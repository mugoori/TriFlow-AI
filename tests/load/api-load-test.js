/**
 * k6 Load Test Script for TriFlow AI API
 *
 * Tests the following endpoints:
 * - /api/v1/bi/statcards (Dashboard)
 * - /api/v1/sensors (Sensor data)
 * - /api/v1/agents/chat (Agent chat)
 *
 * Usage:
 *   k6 run tests/load/api-load-test.js
 *
 * With custom options:
 *   k6 run --vus 50 --duration 5m tests/load/api-load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');
const requestCount = new Counter('requests');

// Test configuration
export const options = {
  // Load test stages
  stages: [
    { duration: '2m', target: 50 },   // Ramp-up to 50 users
    { duration: '5m', target: 100 },  // Stay at 100 users for 5 minutes
    { duration: '2m', target: 150 },  // Spike to 150 users
    { duration: '3m', target: 100 },  // Back to 100 users
    { duration: '2m', target: 0 },    // Ramp-down to 0
  ],

  // Performance thresholds
  thresholds: {
    'http_req_duration': ['p(95)<2000', 'p(99)<3000'], // P95 < 2s, P99 < 3s
    'http_req_failed': ['rate<0.05'],                   // Error rate < 5%
    'errors': ['rate<0.05'],                            // Custom error rate < 5%
    'request_duration': ['p(95)<2000'],                 // Custom metric
  },
};

// Base URL (can be overridden via environment variable)
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Sample API key for testing (replace with valid key or use auth)
const API_KEY = __ENV.API_KEY || 'tfk_test_key_123';

// Request headers
const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

/**
 * Main test scenario
 * Simulates realistic user behavior
 */
export default function () {
  // Scenario 1: Dashboard load (80% of users)
  if (Math.random() < 0.8) {
    testDashboardLoad();
  }

  // Scenario 2: Sensor data query (60% of users)
  if (Math.random() < 0.6) {
    testSensorDataQuery();
  }

  // Scenario 3: Agent chat (30% of users)
  if (Math.random() < 0.3) {
    testAgentChat();
  }

  // Think time between requests (1-3 seconds)
  sleep(Math.random() * 2 + 1);
}

/**
 * Test dashboard statcards endpoint
 */
function testDashboardLoad() {
  const startTime = new Date();

  const response = http.get(`${BASE_URL}/api/v1/bi/statcards`, {
    headers,
    tags: { name: 'DashboardStatCards' },
  });

  const duration = new Date() - startTime;
  requestDuration.add(duration);
  requestCount.add(1);

  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response has data': (r) => r.json('data') !== null,
    'response time < 2s': (r) => r.timings.duration < 2000,
  });

  if (!success) {
    errorRate.add(1);
    console.error(`Dashboard load failed: ${response.status} ${response.body}`);
  } else {
    errorRate.add(0);
  }
}

/**
 * Test sensor data endpoint
 */
function testSensorDataQuery() {
  const startTime = new Date();

  // Query sensors with various filters
  const params = {
    limit: 100,
    offset: Math.floor(Math.random() * 500),
    line_code: ['LINE_A', 'LINE_B', 'LINE_C'][Math.floor(Math.random() * 3)],
  };

  const response = http.get(`${BASE_URL}/api/v1/sensors?${new URLSearchParams(params)}`, {
    headers,
    tags: { name: 'SensorDataQuery' },
  });

  const duration = new Date() - startTime;
  requestDuration.add(duration);
  requestCount.add(1);

  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response is array': (r) => Array.isArray(r.json()),
    'response time < 1.5s': (r) => r.timings.duration < 1500,
  });

  if (!success) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

/**
 * Test agent chat endpoint
 */
function testAgentChat() {
  const startTime = new Date();

  // Sample chat messages
  const messages = [
    'LINE_A 온도 확인해줘',
    '오늘 생산량 얼마야?',
    '불량이 가장 많은 라인 알려줘',
    '최근 1주일 트렌드 분석해줘',
  ];

  const payload = JSON.stringify({
    message: messages[Math.floor(Math.random() * messages.length)],
    context: {},
    tenant_id: 'test-tenant',
  });

  const response = http.post(`${BASE_URL}/api/v1/agents/chat`, payload, {
    headers,
    tags: { name: 'AgentChat' },
  });

  const duration = new Date() - startTime;
  requestDuration.add(duration);
  requestCount.add(1);

  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response has agent_name': (r) => r.json('agent_name') !== null,
    'response time < 5s': (r) => r.timings.duration < 5000,
  });

  if (!success) {
    errorRate.add(1);
    console.error(`Agent chat failed: ${response.status}`);
  } else {
    errorRate.add(0);
  }
}

/**
 * Setup function - runs once at the beginning
 */
export function setup() {
  console.log(`Starting load test against: ${BASE_URL}`);
  console.log('Test configuration:', JSON.stringify(options.stages, null, 2));

  // Health check
  const health = http.get(`${BASE_URL}/health`);
  if (health.status !== 200) {
    console.error('Health check failed! Server may not be running.');
  }

  return { startTime: new Date().toISOString() };
}

/**
 * Teardown function - runs once at the end
 */
export function teardown(data) {
  console.log(`Load test completed. Started at: ${data.startTime}`);
}
