const loadTrackerDB = require('@ghostery/trackerdb');

// Initialize the tracker database
let trackerDB = null;
let isInitializing = false;
let initPromise = null;

async function initTrackerDB() {
  if (isInitializing) {
    return initPromise;
  }
  
  isInitializing = true;
  initPromise = loadTrackerDB().then(db => {
    trackerDB = db;
    console.error('Ghostery TrackerDB loaded successfully');
    return db;
  }).catch(err => {
    console.error(`Error loading TrackerDB: ${err.message}`);
    throw err;
  }).finally(() => {
    isInitializing = false;
  });
  
  return initPromise;
}

// Initialize on startup
initTrackerDB();

const readline = require('readline');
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

rl.on('line', async (url) => {
  try {
    // Make sure DB is initialized
    if (!trackerDB) {
      await initTrackerDB();
    }
    
    // Use the correct API method from TrackerDB
    const result = await trackerDB.analyzeUrl(url);
    console.log(JSON.stringify(result));
  } catch (error) {
    console.error(`Error analyzing URL: ${error.message}`);
    console.log('{}'); // Return empty object on error
  }
});

console.error('Ghostery bridge ready');
