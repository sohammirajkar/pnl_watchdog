# Infrastructure Economics: Complete Guide

## What is Kyle's Lambda?

Kyle's Lambda measures **price impact per unit of signed volume**.

Formula: λ = ΔPrice / ΔVolume

**Interpretation:**

- Lambda = 1.23 → Price moves ₹1.23 per crore traded
- Lambda = 4.88 → Price moves ₹4.88 per crore traded  
- Higher Lambda = worse execution (more impact for same trade size)

## Cost Breakdown: Why Institutions Have <1ms

| Component | Cost/Year | Required |
|-----------|-----------|----------|
| Co-location server | ₹5-10 Lakh | Per exchange |
| Custom FIX engine | ₹50 Lakh | One-time |
| Dedicated connectivity | ₹10-20 Lakh | Per exchange |
| Operations | ₹20-30 Lakh | Ongoing |
| **Total (1 exchange)** | **₹100+ Lakh** | **Minimum** |

**Justification for Institutions:**

- AUM: ₹1000+ Crore
- Trading volume: ₹1000+ Crore/year
- Friction cost without optimization: ₹100+ Crore/year
- Spend ₹1 Cr to save ₹100 Cr = **100x ROI**

**Why Retail Can't:**

- Retail AUM: ₹25 Lakh
- Trading volume: ₹50 Lakh/year
- Friction cost: ₹2,480/year
- Cost to fix: ₹100,000+/year = **40x cost vs benefit**

The math doesn't work. So HTTP brokers exist.
