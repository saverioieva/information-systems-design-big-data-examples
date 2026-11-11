'use strict'
const AWS = require("aws-sdk");

// Set the region
AWS.config.update({ region: "us-east-1" });

// Create an SQS service object
const sqs = new AWS.SQS({ apiVersion: "2012-11-05" });

const lambda_handler = async (event) => {
	console.log(event);
	const queueName = event.queryStringParameters.name;
	
	const queueURL = `https://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/${queueName}`;
	
	const params = {
		MaxNumberOfMessages: 5,
		MessageAttributeNames: ["All"],
		QueueUrl: queueURL
	};
	
	const data = await sqs.receiveMessage(params).promise();
	
	return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: data }),
    };
}

    
module.exports = {
    lambda_handler,
}