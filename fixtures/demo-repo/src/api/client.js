/**
 * Blast Radius Demo API Client Module
 *
 * This module demonstrates an HTTP client wrapper using Axios.
 * In older Axios (< 1.6.0), the auth parameter accepted colon-separated strings.
 * In Axios >= 1.6.0, auth strictly requires { username, password }.
 */

// Simulated Axios interface for lightweight, deterministic execution
const axios = {
  create(config = {}) {
    return {
      defaults: {
        baseURL: config.baseURL || 'https://api.example.com',
        auth: config.auth,
        headers: config.headers || {}
      },
      get(url) {
        return Promise.resolve({ data: { ok: true, url } });
      },
      post(url, data) {
        return Promise.resolve({ data: { ok: true, data } });
      }
    };
  }
};

/**
 * Service initialization and configuration helpers.
 *
 * Note: Lines 30-39 provide context padding so that
 * createAuthenticatedClient begins precisely at line 40.
 */
// Context line 34
// Context line 35
// Context line 36
// Context line 37
// Context line 38
// Context line 39
function createAuthenticatedClient(credentials) {
  const client = axios.create({ auth: credentials });
  return client;
}

module.exports = {
  axios,
  createAuthenticatedClient
};
