"""Standalone PostgreSQL-backed Commutative Updates and Version File examples.

Run via `make commutative` or `make version-file`. These experiments
use independent database tables and do not change Saga orders or payments.
"""
import argparse
import os
from uuid import uuid4

from app.adapters.outbound.postgres_store import PostgresSagaStore


def run_commutative(store):
    a, b = 'credit-a-' + str(uuid4()), 'credit-b-' + str(uuid4())
    with store.transaction() as tx:
        tx.initialize_credit(a, 100)
        tx.initialize_credit(b, 100)
        left = [tx.adjust_credit(a, 'left-credit-' + a, +25),
                tx.adjust_credit(a, 'left-debit-' + a, -10)]
        right = [tx.adjust_credit(b, 'right-debit-' + b, -10),
                 tx.adjust_credit(b, 'right-credit-' + b, +25)]
        # Diagnostic values are shown if a database-backed run diverges.
        # This also checks each intermediate balance, not only the final one.
        expected_left, expected_right = [125, 115], [90, 115]
        if left != expected_left or right != expected_right:
            raise AssertionError(
                'Commutative Updates diverged: '
                f'left={left!r} (expected {expected_left!r}), '
                f'right={right!r} (expected {expected_right!r}). '
                'Check adjust_credit() and the running container image.'
            )
        after_duplicate = tx.adjust_credit(a, 'left-credit-' + a, +25)
        if after_duplicate != 115:
            raise AssertionError(
                f'Duplicated credit changed balance: {after_duplicate!r} != 115'
            )
        compensated = tx.adjust_credit(a, 'compensate-' + a, -25)
        if compensated != 90:
            raise AssertionError(
                f'Compensation gave {compensated!r}, expected 90'
            )
    print('COMMUTATIVE: +25,-10 -> 115; -10,+25 -> 115')
    print('Idempotent duplicate +25 -> 115; compensation -25 -> 90')
    print('Note: arithmetic commutativity alone does not authorize an overdraft.')


def run_version_file(store):
    stream = 'version-file-' + str(uuid4())
    with store.transaction() as tx:
        # Arrival order: seq 3 (ADD 7), seq 1 (SET 10), seq 2 (MULTIPLY 2).
        # Logical order is non-commutative: SET 10 * 2 + 7 = 27.
        pending = tx.apply_versioned(stream, 3, 'ADD', 7)
        assert pending == {'nextSequence': 1, 'total': 0, 'buffered': 1}
        first = tx.apply_versioned(stream, 1, 'SET', 10)
        assert first == {'nextSequence': 2, 'total': 10, 'buffered': 1}
        resolved = tx.apply_versioned(stream, 2, 'MULTIPLY', 2)
        assert resolved == {'nextSequence': 4, 'total': 27, 'buffered': 0}
        duplicate = tx.apply_versioned(stream, 3, 'ADD', 7)
        assert duplicate == resolved
    print('VERSION FILE: seq 3 (ADD 7) arrives first -> buffered, total 0')
    print('Seq 1 (SET 10) -> total 10; seq 2 (MULTIPLY 2) -> apply 2 then 3 -> total 27')
    print('Without ordering, arrival-order ADD 7, SET 10, MULTIPLY 2 -> 20 (incorrect).')
    print('Duplicate seq 3 -> no repeated effect; durable event log in PostgreSQL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('demo', choices=('commutative', 'version-file'))
    args = parser.parse_args()
    store = PostgresSagaStore('orchestrator', os.environ['DATABASE_URL'])
    store.initialize()
    if args.demo == 'commutative':
        run_commutative(store)
    else:
        run_version_file(store)


if __name__ == '__main__':
    main()
