Rebuild the buyer database for project p_1778324230_fd9650 using ONLY verifiable, real institutional buyers.

The previous 50-buyer CSV was FAKE — all emails were @example domains and all phones were 555-XXXX. The 25-buyer list had some real-looking data but needs verification.

Sources to use:
- SEC EDGAR 10-K filings for REITs — actual tickers: INVH, AMH, TCN, MAA, CPT, AVB, EQR, UDR
- iBuyer public websites: opendoor.com, offerpad.com
- BiggerPockets actual marketplace posts
- LinkedIn company pages for known acquisition directors at real firms

Return 25 REAL buyers with:
- company name
- REAL acquisition contact name (from LinkedIn or company directory)
- REAL company domain email (format only, do not guess individual emails)
- phone (use main company line from website)
- buy box
- state markets
- source URL

Flag any entry where individual email or phone cannot be verified as "needs outreach via LinkedIn/website form".

Save the final output as BUYER_DATABASE_VERIFIED.md in the project outbox.
