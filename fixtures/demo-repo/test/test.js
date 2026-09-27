const assert = require('node:assert');
const { createAuthenticatedClient } = require('../src/api/client');

console.log('Running Blast Radius Demo App Test Suite...');

const client = createAuthenticatedClient('admin:secretpassword123');

// In modern Axios (>= 1.6.0), auth MUST be an object with username and password
assert(client.defaults.auth !== undefined, 'auth config should be present');
assert.strictEqual(
  typeof client.defaults.auth,
  'object',
  `Expected client.defaults.auth to be an object (Axios >= 1.6.0 contract), but got: ${typeof client.defaults.auth} (${client.defaults.auth})`
);
assert(client.defaults.auth !== null, 'client.defaults.auth must not be null');
assert.strictEqual(
  client.defaults.auth.username,
  'admin',
  `Expected username 'admin', got: ${client.defaults.auth.username}`
);
assert.strictEqual(
  client.defaults.auth.password,
  'secretpassword123',
  `Expected password 'secretpassword123', got: ${client.defaults.auth.password}`
);

console.log('All tests PASSED: Auth configuration conforms to Axios >= 1.6.0 specification.');
