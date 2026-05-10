DIRECTIVE: Build a verified institutional buyer database for project p_1778324230_fd9650.

The previous attempt was TRUNCATED at entry #4. You must produce 25 COMPLETE, verifiable buyer entries.

## RULES
- ONLY real, publicly verifiable companies
- NO 555 phone numbers
- NO @example.com / @fake.com / guessed individual emails
- Use REAL company main phone numbers from actual websites
- Use REAL company domain email FORMATS (e.g., acquisitions@company.com) — do not guess personal emails
- If individual contact cannot be verified, flag as "needs outreach via LinkedIn/website form"

## SOURCES (use these, no others)
1. SEC EDGAR 10-K filings: INVH, AMH, TCN, CPT, AVB, EQR, UDR, MAA
2. iBuyer websites: opendoor.com, offerpad.com
3. BiggerPockets marketplace (free public posts)
4. County recorder cash-deed analysis

## FORMAT PER ENTRY
```
### #. Company Name
- **Company**: [name] ([ticker if REIT])
- **Contact**: [real name from SEC/IR page] — verified via [source]
- **Email Format**: [real format, e.g., acquisitions@company.com]
- **Phone**: [real main company line]
- **Buy Box**: [price range, property types, condition]
- **Markets**: [states/metros]
- **Source**: [URL]
- **Status**: ✅ Verified OR ⚠️ needs outreach
```

Write 25 entries. Do NOT truncate. Do NOT use bash blocks. Write plain markdown.

## EXAMPLE (verified)
### 1. Invitation Homes
- **Company**: Invitation Homes Inc. (NYSE: INVH)
- **Contact**: Dallas Tanner — CEO, verified via SEC DEF 14A
- **Email Format**: acquisitions@invitationhomes.com
- **Phone**: (469) 223-2300
- **Buy Box**: SFR $200K-$800K, built 1990+, 3-5 bed / 2+ bath
- **Markets**: TX, FL, CA, AZ, NV, NC, SC, TN, GA, CO
- **Source**: https://ir.invitationhomes.com
- **Status**: ✅ Verified

Continue through #25.