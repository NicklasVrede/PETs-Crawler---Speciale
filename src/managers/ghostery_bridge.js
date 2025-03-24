
const { urlDb } = require('@ghostery/trackerdb');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

rl.on('line', async (url) => {
  try {
    const result = await urlDb.analyzeUrl(url);
    console.log(JSON.stringify(result));
  } catch (error) {
    console.log('{}');
  }
});

console.error('Ghostery bridge ready');
