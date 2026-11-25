#!/usr/bin/env node
const cdk = require('aws-cdk-lib');
const { StepFunctionStack } = require('../lib/step_function-stack');

const app = new cdk.App();
new StepFunctionStack(app, 'StepFunctionStack');
