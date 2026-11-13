import json
import unittest
from bridge.domain.routing import translate, decode_outbox_value


class BridgeContractTests(unittest.TestCase):
    def test_created_event_routing(self):
        value = {'eventId': 'e1','type': 'OrderCreated','orderId': 'o1'}
        routed = translate(json.dumps(value).encode())
        self.assertEqual(routed.routing_key, 'order.created')
        self.assertEqual(routed.event_id, 'e1')
        self.assertEqual(json.loads(routed.payload), value)

    def test_escaped_json_and_approved(self):
        value = {'eventId': 'e2','type': 'OrderApproved','orderId': 'o2'}
        escaped = json.dumps(json.dumps(value)).encode()
        self.assertEqual(decode_outbox_value(escaped), value)
        self.assertEqual(translate(escaped).routing_key, 'order.approved')

    def test_unknown_event_fails(self):
        with self.assertRaises(ValueError):
            translate(json.dumps({'eventId':'e','orderId':'o','type':'Other'}).encode())


if __name__ == '__main__':
    unittest.main()
