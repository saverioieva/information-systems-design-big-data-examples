const cdk = require('aws-cdk-lib');
const sns = require('aws-cdk-lib/aws-sns');
const subs = require('aws-cdk-lib/aws-sns-subscriptions');
const sqs = require('aws-cdk-lib/aws-sqs');

class QueueSubscriptionStack extends cdk.Stack {
  /**
   * @param {cdk.App} scope
   * @param {string} id
   * @param {cdk.StackProps=} props
   */
  constructor(scope, id, props) {
    super(scope, id, props);

    const queue = new sqs.Queue(this, 'QueueSubscriptionQueue', {
      queueName: 'my-queue',
      visibilityTimeout: cdk.Duration.seconds(30)
    });

    const topic = new sns.Topic(this, 'QueueSubscriptionTopic', {
      topicName: 'my-topic'
    });

    topic.addSubscription(new subs.SqsSubscription(queue));
  }
}

module.exports = { QueueSubscriptionStack }
