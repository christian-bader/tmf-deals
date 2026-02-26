/**
 * Email templates for different outreach scenarios.
 */

const TEMPLATES = {
  'sale-listing': {
    name: 'Active Listing (Seller Rep)',
    body: `I'm with Trinity Mortgage Fund, a private lender based in Del Mar. We help agents keep deals together by providing hard money purchase, bridge, and construction loans for investment properties throughout coastal San Diego.

We can help in situations where:

• A buyer needs fast financing to close
• Your seller wants to refinance or pull cash out
• A buyer plans to renovate or build
• Traditional financing is too slow or falls through

Typical Terms:

• $1M–$10M loan amounts
• Up to 75% of market value
• No appraisals, personal financials, or guarantees
• Close in as little as 5–10 days
• 12–24 month terms
• Interest-only payments

We've recently helped agents close deals like:

• $3.6M construction loan on an oceanfront lot in Encinitas
• $2.55M purchase loan on a townhome in Coronado
• $1.5M refinance on a home in La Jolla

If you have a buyer interested in this property — or any upcoming listings where fast financing could help — I'd be happy to be a resource.

Best,

Dan McColl
Director of Construction Lending
Trinity Mortgage Fund
(858) 775-0962
dan@trinitysd.com
DRE#02215901 - CA DFPI#60DBO-59425`,
  },
  
  'sale-pending': {
    name: 'Pending/Contingent (Seller Rep)',
    body: `I'm reaching out because I work with many agents who like having a reliable backup lending option in place, just in case a buyer's financing gets delayed or falls through.

I'm with Trinity Mortgage Fund, a Del Mar–based private lender. We provide fast hard money purchase, bridge, and construction loans for investment properties, and we're often able to step in and help agents keep deals together when timing is critical.

Key highlights:

• $1M–$10M loan amounts
• Up to 75% of market value
• No appraisals, personal financials, or guarantees
• Close in as little as 5–10 days
• 12–24 month terms
• Interest-only payments

We've recently helped agents salvage and close transactions like:

• $3.6M construction loan on an oceanfront lot in Encinitas (60% LTV)
• $3.771M purchase loan on a 5,000 SF home in Pacific Highlands (75% LTV)
• $2.65M purchase loan on a vacant lot in La Jolla (65% LTV)

Hopefully your current escrow goes smoothly, but if you ever need a quick backup solution for this deal or a future one, I'd be happy to help.

Would it make sense to connect so you have a reliable option in your back pocket?

Best,

Dan McColl
Director of Construction Lending
Trinity Mortgage Fund
(858) 775-0962
dan@trinitysd.com
DRE#02215901 - CA DFPI#60DBO-59425`,
  },
  
  'buyer-closed': {
    name: 'Recently Closed (Buyer Rep)',
    body: `I'm reaching out because I work with a lot of agents whose buyers end up needing fast financing after close — whether it's for renovations, a bridge to their next acquisition, or pulling equity out quickly.

I'm with Trinity Mortgage Fund, a Del Mar–based private lender. We provide hard money purchase, bridge, and construction loans for investment properties throughout coastal Southern California.

If your client is planning any work on the property or looking at their next deal, we can often help where traditional financing is too slow or too complicated.

Key highlights:

• $1M–$10M loan amounts
• Up to 75% of market value
• No appraisals, personal financials, or guarantees
• Close in as little as 5–10 days
• 12–24 month terms
• Interest-only payments

Recent deals we've helped close:

• $3.6M construction loan on an oceanfront lot in Encinitas (60% LTV)
• $3.771M purchase loan on a 5,000 SF home in Pacific Highlands (75% LTV)
• $2.65M purchase loan on a vacant lot in La Jolla (65% LTV)

If you ever have a client who needs to move fast — or if you're working with investors who buy frequently — I'd love to be a resource.

Would it make sense to connect briefly?

Best,

Dan McColl
Director of Construction Lending
Trinity Mortgage Fund
(858) 775-0962
dan@trinitysd.com
DRE#02215901 - CA DFPI#60DBO-59425`,
  },
};

/**
 * Get template by type.
 */
function getTemplate(templateType) {
  return TEMPLATES[templateType] || TEMPLATES['sale-listing'];
}

/**
 * Classify which template to use based on broker's listings.
 */
function classifyTemplate(listings) {
  if (!listings || listings.length === 0) {
    return 'sale-listing';
  }
  
  // Check if any listings are sold where broker was buyer rep
  const buyerDeals = listings.filter(l => l.status === 'sold' && l.role === 'buyer');
  if (buyerDeals.length > 0) {
    return 'buyer-closed';
  }
  
  // Check for pending/contingent (seller rep)
  const pending = listings.filter(l => 
    ['pending', 'contingent'].includes((l.status || '').toLowerCase())
  );
  if (pending.length > 0) {
    return 'sale-pending';
  }
  
  // Default: active listing (seller rep)
  return 'sale-listing';
}

/**
 * Get first name from full name.
 */
function getFirstName(fullName) {
  if (!fullName) return 'there';
  return fullName.trim().split(' ')[0];
}
