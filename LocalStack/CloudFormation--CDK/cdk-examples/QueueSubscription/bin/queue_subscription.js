#!/usr/bin/env node
const cdk = require('aws-cdk-lib/core');
const { QueueSubscriptionStack } = require('../lib/queue_subscription-stack');
const { LambdaQueueStack } = require('../lib/lambda_queue.js');

const app = new cdk.App();
new QueueSubscriptionStack(app, 'QueueSubscriptionStack');
new LambdaQueueStack(app, 'LambdaQueueStack');
