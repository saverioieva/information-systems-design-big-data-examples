"""Durable RabbitMQ workflows for commutativity and Version File.

The Order Service coordinates command/reply messages. Accounting owns its
credit ledger; Kitchen owns the Version File. No test-only Outbox gates are
used in these workflows. Every transition and outgoing intent commits locally.
"""
from uuid import uuid4


def new_id():
    return str(uuid4())


class CountermeasureWorkflows:
    def __init__(self, store):
        self.store = store

    def start_commutative(self):
        run_id = new_id()
        # Two independent, overlapping credit-adjustment workflows per account.
        # Each is Consumer verification -> Accounting update, with a distinct saga ID.
        cases = [('A', 25), ('A', -10), ('B', -10), ('B', 25)]
        with self.store.transaction() as tx:
            tx.create_countermeasure_run(run_id, 'commutative', 'INITIAL')
            for label, delta in cases:
                step_id, saga_id, operation_id = new_id(), new_id(), new_id()
                account_id = f'{run_id}-{label}'
                data = {'accountId': account_id, 'case': label, 'delta': delta,
                        'operationId': operation_id}
                tx.create_countermeasure_step(run_id, step_id, saga_id,
                    'credit', 'VERIFYING', data)
                tx.enqueue('command.consumer', saga_id,
                    action='VerifyConsumer', customerId='CUST_1',
                    countermeasureType='commutative', runId=run_id,
                    stepId=step_id, sagaId=saga_id)
        return {'runId': run_id, 'kind': 'commutative', 'status': 'INITIAL',
                'location': f'/countermeasures/{run_id}'}

    def start_version_file(self):
        run_id = new_id()
        # One distributed workflow: Consumer verification, then three commands
        # intentionally sent 3,1,2 to Kitchen over RabbitMQ.
        with self.store.transaction() as tx:
            tx.create_countermeasure_run(run_id, 'version-file', 'VERIFYING')
            for sequence, operation, value in ((3, 'ADD', 7), (1, 'SET', 10),
                                               (2, 'MULTIPLY', 2)):
                step_id, saga_id = new_id(), new_id()
                data = {'streamId': run_id, 'sequence': sequence,
                        'operation': operation, 'value': value}
                tx.create_countermeasure_step(run_id, step_id, saga_id,
                    'version', 'PENDING', data)
            tx.enqueue('command.consumer', run_id, action='VerifyConsumer',
                customerId='CUST_1', countermeasureType='version-file',
                runId=run_id, stepId=None, sagaId=run_id)
        return {'runId': run_id, 'kind': 'version-file', 'status': 'VERIFYING',
                'location': f'/countermeasures/{run_id}'}

    def get(self, run_id):
        with self.store.transaction() as tx:
            return tx.get_countermeasure_run(run_id)

    def _dispatch_credit(self, tx, step, kind='AdjustCredit'):
        data = step['data']
        tx.enqueue('command.accounting', step['sagaId'], action=kind,
            countermeasureType='commutative', runId=step['runId'],
            stepId=step['stepId'], sagaId=step['sagaId'],
            accountId=data['accountId'], operationId=data['operationId'],
            delta=data['delta'], openingBalance=100)

    def _dispatch_version(self, tx, run_id, sequence):
        run = tx.get_countermeasure_run(run_id)
        step = next(s for s in run['steps'] if s['data'].get('sequence') == sequence)
        if step['status'] != 'PENDING':
            return
        tx.update_countermeasure_step(step['stepId'], 'QUEUED')
        data = step['data']
        tx.enqueue('command.kitchen', step['sagaId'], action='ApplyVersioned',
            countermeasureType='version-file', runId=run_id,
            stepId=step['stepId'], sagaId=step['sagaId'],
            streamId=data['streamId'], sequence=data['sequence'],
            operation=data['operation'], value=data['value'])

    def handle_message(self, message):
        with self.store.transaction() as tx:
            mid = message['messageId']
            if tx.seen(mid):
                return
            run_id = message['runId']
            run = tx.get_countermeasure_run(run_id)
            if run is None:
                raise ValueError(f'Unknown countermeasure run: {run_id}')
            kind, action = run['kind'], message['action']
            step_id = message.get('stepId')
            step = next((s for s in run['steps'] if s['stepId'] == step_id), None)

            if action == 'CountermeasureRejected':
                tx.set_countermeasure_run_stage(run_id, 'REJECTED')
            elif action == 'CountermeasureVerified':
                if kind == 'commutative':
                    if step is not None and step['status'] == 'VERIFYING':
                        tx.update_countermeasure_step(step_id, 'QUEUED')
                        self._dispatch_credit(tx, step)
                elif run['status'] == 'VERIFYING':
                    tx.set_countermeasure_run_stage(run_id, 'RUNNING')
                    self._dispatch_version(tx, run_id, 3)
            elif action == 'CountermeasureCreditAdjusted' and kind == 'commutative':
                if step is not None and step['status'] == 'QUEUED':
                    result = {'balance': message['balance'],
                              'accountId': message['accountId'],
                              'delta': message['delta']}
                    tx.update_countermeasure_step(step_id, 'DONE', result)
                    updated = tx.get_countermeasure_run(run_id)
                    if run['status'] == 'INITIAL' and all(
                        s['status'] == 'DONE' for s in updated['steps']
                        if s['name'] == 'credit'
                    ):
                        original = next(s for s in updated['steps'] if
                            s['name'] == 'credit' and s['data']['case'] == 'A' and
                            s['data']['delta'] == 25)
                        duplicate = {
                            'accountId': original['data']['accountId'],
                            'case': 'A', 'delta': 25,
                            'operationId': original['data']['operationId']}
                        new_step = new_id()
                        duplicate_saga = new_id()
                        tx.create_countermeasure_step(run_id, new_step,
                            duplicate_saga, 'duplicate', 'QUEUED', duplicate)
                        tx.set_countermeasure_run_stage(run_id, 'DUPLICATE')
                        self._dispatch_credit(tx, {'data': duplicate, 'runId': run_id,
                            'stepId': new_step, 'sagaId': duplicate_saga})
                    elif run['status'] == 'DUPLICATE' and step['name'] == 'duplicate':
                        compensation = {'accountId': step['data']['accountId'],
                            'case': 'A', 'delta': -25, 'operationId': new_id()}
                        new_step, compensation_saga = new_id(), new_id()
                        tx.create_countermeasure_step(run_id, new_step,
                            compensation_saga, 'compensation', 'QUEUED', compensation)
                        tx.set_countermeasure_run_stage(run_id, 'COMPENSATING')
                        self._dispatch_credit(tx, {'data': compensation, 'runId': run_id,
                            'stepId': new_step, 'sagaId': compensation_saga})
                    elif run['status'] == 'COMPENSATING' and step['name'] == 'compensation':
                        tx.set_countermeasure_run_stage(run_id, 'COMPLETED')
            elif action == 'CountermeasureVersionApplied' and kind == 'version-file':
                if step is not None and step['status'] == 'QUEUED':
                    result = {'nextSequence': message['nextSequence'],
                        'total': message['total'], 'buffered': message['buffered']}
                    tx.update_countermeasure_step(step_id, 'DONE', result)
                    sequence = int(step['data']['sequence'])
                    if sequence == 3:
                        self._dispatch_version(tx, run_id, 1)
                    elif sequence == 1:
                        self._dispatch_version(tx, run_id, 2)
                    elif sequence == 2:
                        tx.set_countermeasure_run_stage(run_id, 'COMPLETED')
            else:
                raise ValueError(f'Unexpected countermeasure reply: {kind} / {action}')
            tx.mark_seen(mid)
