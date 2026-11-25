#!/usr/bin/env node
const cdk = require('aws-cdk-lib/core');
const { QueueSubscription2Stack } = require('../lib/queue_subscription2-stack');

const app = new cdk.App();
new QueueSubscription2Stack(app, 'QueueSubscription2Stack');

