/**
 * Supabase REST API wrapper for Google Apps Script.
 */

function supabaseFetch(endpoint, options = {}) {
  const config = getConfig();
  const url = `${config.SUPABASE_URL}/rest/v1/${endpoint}`;
  
  const defaultHeaders = {
    'apikey': config.SUPABASE_KEY,
    'Authorization': `Bearer ${config.SUPABASE_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': options.prefer || 'return=representation',
  };
  
  const fetchOptions = {
    method: options.method || 'GET',
    headers: { ...defaultHeaders, ...options.headers },
    muteHttpExceptions: true,
  };
  
  if (options.body) {
    fetchOptions.payload = JSON.stringify(options.body);
  }
  
  const response = UrlFetchApp.fetch(url, fetchOptions);
  const status = response.getResponseCode();
  const text = response.getContentText();
  
  if (status >= 400) {
    throw new Error(`Supabase error (${status}): ${text}`);
  }
  
  return text ? JSON.parse(text) : null;
}

/**
 * Fetch outreach opportunities (brokers not contacted in 30 days).
 */
function fetchOpportunities(limit = 50) {
  return supabaseFetch(`outreach_opportunities?limit=${limit}`);
}

/**
 * Fetch a single broker by ID.
 */
function fetchBroker(brokerId) {
  const result = supabaseFetch(`brokers?id=eq.${brokerId}`);
  return result && result.length > 0 ? result[0] : null;
}

/**
 * Fetch suggested emails by status.
 */
function fetchSuggestedEmails(status = 'approved', limit = 50) {
  return supabaseFetch(`suggested_emails?status=eq.${status}&limit=${limit}&order=created_at.desc`);
}

/**
 * Insert a new suggested email.
 */
function insertSuggestedEmail(data) {
  return supabaseFetch('suggested_emails', {
    method: 'POST',
    body: data,
  });
}

/**
 * Update a suggested email.
 */
function updateSuggestedEmail(id, data) {
  return supabaseFetch(`suggested_emails?id=eq.${id}`, {
    method: 'PATCH',
    body: data,
  });
}

/**
 * Insert a sent email log.
 */
function insertSentEmailLog(data) {
  return supabaseFetch('sent_email_logs', {
    method: 'POST',
    body: data,
  });
}

/**
 * Insert a suppression log.
 */
function insertSuppressionLog(data) {
  return supabaseFetch('outreach_suppression_logs', {
    method: 'POST',
    body: data,
  });
}

/**
 * Test Supabase connection.
 */
function testSupabase() {
  try {
    validateConfig();
    const opportunities = fetchOpportunities(5);
    console.log('✓ Supabase connected');
    console.log(`  Found ${opportunities.length} opportunities`);
    if (opportunities.length > 0) {
      console.log('  Sample:', opportunities[0].name, '-', opportunities[0].email);
    }
  } catch (e) {
    console.error('✗ Supabase error:', e.message);
  }
}
