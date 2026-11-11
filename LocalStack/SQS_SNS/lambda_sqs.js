'use strict'

const lambda_handler = async (event) => {
	console.log(event);
	
	for (const record of event.Records) {
		await processMessageAsync(record);
	}
	console.info("done");
}

async function processMessageAsync(record) {
  try {
    console.log(`Processed message ${record.body}`);
    await Promise.resolve(1); //Placeholder for actual async work
  } catch (err) {
    console.error("An error occurred");
    throw err;
  }
}
    
module.exports = {
    lambda_handler,
}