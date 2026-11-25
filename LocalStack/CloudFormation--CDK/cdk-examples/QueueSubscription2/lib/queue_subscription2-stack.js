const cdk = require('aws-cdk-lib/core');
const sns = require('aws-cdk-lib/aws-sns');
const subs = require('aws-cdk-lib/aws-sns-subscriptions');
const sqs = require('aws-cdk-lib/aws-sqs');

const lambda = require('aws-cdk-lib/aws-lambda');
const eventsources = require('aws-cdk-lib/aws-lambda-event-sources');


class QueueSubscription2Stack extends cdk.Stack {
  /**
   * @param {cdk.App} scope
   * @param {string} id
   * @param {cdk.StackProps=} props
   */
  constructor(scope, id, props) {
    super(scope, id, props);

    const queue = new sqs.Queue(this, 'QueueSubscription2Queue', {
      queueName: "my-queue",
      visibilityTimeout: cdk.Duration.seconds(300)
    });

    const topic = new sns.Topic(this, 'QueueSubscription2Topic'{
      topicName: "my-topic"
    });

    topic.addSubscription(new subs.SqsSubscription(queue));

    const fn = new lambda.Function(this, 'MyFunction', {
      code: lambda.Code.fromAsset('lambdas'),
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'lambda_sqs.lambda_handler',
      functionName: 'process-event'
    });

    fn.addEventSource(new eventsources.SqsEventSource(queue));
  }
}

module.exports = { QueueSubscription2Stack }
