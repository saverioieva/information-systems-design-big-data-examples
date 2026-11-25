const cdk = require('aws-cdk-lib');
const sns = require('aws-cdk-lib/aws-sns');
const subs = require('aws-cdk-lib/aws-sns-subscriptions');
const sqs = require('aws-cdk-lib/aws-sqs');
const lambda = require('aws-cdk-lib/aws-lambda');
const eventsources = require('aws-cdk-lib/aws-lambda-event-sources');

class LambdaQueueStack extends cdk.Stack {
  /**
   * @param {cdk.App} scope
   * @param {string} id
   * @param {cdk.StackProps=} props
   */
  constructor(scope, id, props) {
    super(scope, id, props);

    const queue = new sqs.Queue(this, 'QueueSubscriptionQueue', {
      queueName: 'my-queue',
      visibilityTimeout: cdk.Duration.seconds(300)
    });

    const topic = new sns.Topic(this, 'QueueSubscriptionTopic', {
      topicName: 'my-topic'
    });

    topic.addSubscription(new subs.SqsSubscription(queue));

    // create our lambda function resource
    const fn = new lambda.Function(this, 'MyFunction', {
        code: lambda.Code.fromAsset('lambdas'),
        runtime: lambda.Runtime.NODEJS_18_X,
        handler: 'lambda_sqs.lambda_handler',
        functionName: 'process-event'
    });

    // add queue as event source of lambda function
    fn.addEventSource(new eventsources.SqsEventSource(queue));
  }
}

module.exports = { LambdaQueueStack }