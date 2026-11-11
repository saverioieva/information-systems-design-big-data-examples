'use strict'
const AWS = require("aws-sdk");

// Set the region
AWS.config.update({ region: "us-east-1" });

// Create an SQS service object
const sqs = new AWS.SQS({ apiVersion: "2012-11-05" });

const lambda_handler = async (event) => {
	console.log(event);
	const body = JSON.parse(event.body);	
	const queueName = body.name;
	const message = body.message;
	
	const params = {
		MessageBody: message,
		QueueUrl: `https://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/${queueName}`
	};
	
	const data = await sqs.sendMessage(params).promise();
	
	return {
      statusCode: 201,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messageId: data.MessageId }),
    };
}

    
module.exports = {
    lambda_handler,
}