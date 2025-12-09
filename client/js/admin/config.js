const API = "http://127.0.0.1:8000";

// Global State
let isServerOnline = false;
let learnedModels = [];
let lastVectorStatus = 'idle';
let lastGraphStatus = 'idle';
let vectorChartInstance = null;
let graphChartInstance = null;
