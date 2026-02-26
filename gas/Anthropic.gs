/**
 * Anthropic Claude API integration for email personalization.
 */

const ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages';
const CLAUDE_MODEL = 'claude-3-5-sonnet-20241022';

/**
 * Call Anthropic Claude API.
 */
function callClaude(prompt, maxTokens = 500) {
  const config = getConfig();
  
  const response = UrlFetchApp.fetch(ANTHROPIC_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': config.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    payload: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: maxTokens,
      messages: [
        { role: 'user', content: prompt }
      ],
    }),
    muteHttpExceptions: true,
  });
  
  const status = response.getResponseCode();
  const text = response.getContentText();
  
  if (status >= 400) {
    throw new Error(`Anthropic API error (${status}): ${text}`);
  }
  
  const result = JSON.parse(text);
  return result.content[0].text;
}

/**
 * Generate personalized email opener based on broker's listings.
 */
function personalizeEmail(opportunity, templateType) {
  const listings = opportunity.listings || [];
  
  if (listings.length === 0) {
    return null;
  }
  
  const listingsSummary = listings.map(l => {
    const price = l.price ? `$${Number(l.price).toLocaleString()}` : 'price TBD';
    return `- ${l.address} (${price}) - ${l.status}, role: ${l.role}`;
  }).join('\n');
  
  const templateContext = {
    'sale-listing': 'an active listing where they represent the seller',
    'sale-pending': 'a pending/contingent deal where they represent the seller',
    'buyer-closed': 'a recently closed deal where they represented the buyer',
  };
  
  const prompt = `You are writing an outreach email on behalf of Trinity Mortgage Fund, a private hard money lender based in Del Mar, San Diego.

Target: ${opportunity.name} at ${opportunity.brokerage_name || 'their brokerage'}
Email: ${opportunity.email}

Their recent activity:
${listingsSummary}

Context: This is ${templateContext[templateType] || 'a real estate transaction'}.

Write a personalized 1-2 sentence opener for the email that:
1. References the specific property address (use the most relevant one based on template type)
2. Is warm but professional, not salesy
3. Naturally acknowledges their recent activity
4. If they have multiple listings, you can mention that briefly

Template type: ${templateType}

Return ONLY the personalized opener (1-2 sentences), nothing else. Do not include a greeting like "Hi [Name]" - that will be added separately.`;

  return callClaude(prompt, 200);
}

/**
 * Generate email subject line.
 */
function generateSubject(opportunity, templateType) {
  const listings = opportunity.listings || [];
  const primaryListing = listings[0];
  
  if (primaryListing && primaryListing.address) {
    // Extract street address (before the city)
    const streetAddress = primaryListing.address.split(',')[0];
    return `Re: ${streetAddress}`;
  }
  
  return 'Quick question about your recent listing';
}

/**
 * Test Anthropic connection.
 */
function testAnthropic() {
  try {
    validateConfig();
    const response = callClaude('Say "Hello from Claude" and nothing else.', 50);
    console.log('✓ Anthropic connected');
    console.log('  Response:', response);
  } catch (e) {
    console.error('✗ Anthropic error:', e.message);
  }
}
