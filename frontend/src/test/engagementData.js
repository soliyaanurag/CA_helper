// Sample API answers shared by the engagement page tests.

export const CA_ID = "0b5f0b8e-4a8e-4bb1-9f0e-1c2d3e4f5a6b";
export const ENGAGEMENT_ID = "e1e1e1e1-1111-4111-8111-111111111111";

export function engagement(fields) {
  return {
    id: ENGAGEMENT_ID,
    status: "requested",
    ca_profile_id: CA_ID,
    ca_name: "Meera Shah",
    business_name: "Asha Traders",
    quote_reason: null,
    requested_at: "2026-09-27T04:30:00Z",
    expires_at: "2099-01-01T00:00:00Z", // far away, so the sample request never runs out of time
    responded_at: null,
    activated_at: null,
    completed_at: null,
    rating: null,
    items: [
      {
        id: "i1",
        compliance_item_id: "f1",
        form_code: "gstr_3b",
        period_label: "Aug 2026",
        due_date: "2026-09-20",
        service_name: "GSTR-3B filing",
        listed_price: "800.00",
        quoted_price: null,
        agreed_price: null,
      },
      {
        id: "i2",
        compliance_item_id: "f2",
        form_code: "gstr_1",
        period_label: "Aug 2026",
        due_date: "2026-09-11",
        service_name: "GSTR-1 filing",
        listed_price: "600.00",
        quoted_price: null,
        agreed_price: null,
      },
    ],
    ...fields,
  };
}
