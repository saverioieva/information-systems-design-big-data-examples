const cdk = require('aws-cdk-lib/core');
const { Match, Template } = require('aws-cdk-lib/assertions');
const QueueSubscription2 = require('../lib/queue_subscription2-stack');

test('SQS Queue and SNS Topic Created', () => {
  const app = new cdk.App();
  // WHEN
  const stack = new QueueSubscription2.QueueSubscription2Stack(app, 'MyTestStack');
  // THEN
  const template = Template.fromStack(stack);
  template.hasResourceProperties('AWS::SQS::Queue', {
    VisibilityTimeout: 300,
  });

  template.resourceCountIs('AWS::SNS::Topic', 1);
});
