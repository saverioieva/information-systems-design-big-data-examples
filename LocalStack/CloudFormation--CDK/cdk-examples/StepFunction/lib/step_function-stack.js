const cdk = require('aws-cdk-lib');
const lambda = require('aws-cdk-lib/aws-lambda');
const sfn = require('aws-cdk-lib/aws-stepfunctions');
const tasks = require('aws-cdk-lib/aws-stepfunctions-tasks');

class StepFunctionStack extends cdk.Stack {
  /**
   * @param {cdk.App} scope
   * @param {string} id
   * @param {cdk.StackProps=} props
   */
  constructor(scope, id, props) {
    super(scope, id, props);

    // Lambda function to generate a random number
    const generateFn = new lambda.Function(this, 'GenerateNumberLambda', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'lambda_generator.lambda_handler',
      code: lambda.Code.fromAsset('lambdas'),
      functionName: 'generator'
    });

    // Lambda function for even numbers
    const evenFn = new lambda.Function(this, 'EvenLambda', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'lambda_even.lambda_handler',
      code: lambda.Code.fromAsset('lambdas'),
      functionName: 'even'
    });

    // Lambda function for odd numbers
    const oddFn = new lambda.Function(this, 'OddLambda', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'lambda_odd.lambda_handler',
      code: lambda.Code.fromAsset('lambdas'),
      functionName: 'odd'
    });

    // Step Function: Start Task - Generate Random Number
    const generateNumberTask = new tasks.LambdaInvoke(this, 'GenerateRandomNumberTask', {
      lambdaFunction: generateFn,
      outputPath: '$.Payload',
    });

    // Step Function: Even Number
    const evenNumberTask = new tasks.LambdaInvoke(this, 'EvenNumberTask', {
      lambdaFunction: evenFn,
      outputPath: '$.Payload',
    });

    // Step Function: Odd Number
    const oddNumberTask = new tasks.LambdaInvoke(this, 'OddNumberTask', {
      lambdaFunction: oddFn,
      outputPath: '$.Payload',
    });

    const failState = new sfn.Fail(this, 'FailState', {
      error: 'DefaultStateError',
      cause: 'No Matches!',
    });

    const choiceState = new sfn.Choice(this, 'CheckIfEvenOrOdd')
      .when(sfn.Condition.numberEquals('$.number', 0), evenNumberTask)
      .when(sfn.Condition.numberEquals('$.number', 1), oddNumberTask)
      .otherwise(failState);

    // Define Step Function
    const definition = generateNumberTask.next(choiceState);

    // Define State Machine
    const stepFunction = new sfn.StateMachine(this, 'StepFunction', {
      definition,
      timeout: cdk.Duration.minutes(5),
      comment: 'Choice Demo',
      stateMachineName: 'ChoiceStepFunction'
    });
  }
}

module.exports = { StepFunctionStack }
