# Vietnam Stock News Crawling Guide (Objective Data Sources)

## Goal

Build a dataset for AI models predicting stock volatility (T+1, T+5,
T+10) using **objective, primary-source information** rather than human
opinions or aggregated analysis.

------------------------------------------------------------------------

# Source Priority

## Tier 1 -- Primary Sources (Highest Priority)

These are the best sources because they publish original information.

  --------------------------------------------------------------------------
  Source               Data             Recommendation
  -------------------- ---------------- ------------------------------------
  HOSE                 Company          ⭐⭐⭐⭐⭐
                       disclosures      

  HNX                  Company          ⭐⭐⭐⭐⭐
                       disclosures      

  UPCoM                Company          ⭐⭐⭐⭐⭐
                       disclosures      

  VSDC                 Shareholder      ⭐⭐⭐⭐⭐
                       changes,         
                       corporate        
                       actions          

  State Securities     Regulatory       ⭐⭐⭐⭐⭐
  Commission (SSC)     announcements,   
                       penalties        

  Company Investor     Financial        ⭐⭐⭐⭐⭐
  Relations (IR)       reports, AGM     
  websites             documents, board 
                       resolutions      
  --------------------------------------------------------------------------

Recommended document types:

-   Financial statements
-   Board resolutions
-   Extraordinary announcements
-   Dividend announcements
-   Stock issuance
-   ESOP
-   Insider trading
-   Major shareholder changes
-   M&A announcements
-   CEO/CFO changes

------------------------------------------------------------------------

## Tier 2 -- Official News Media

These are generally objective news reports.

Recommended sources:

-   VnEconomy
-   VietnamPlus
-   Báo Đầu tư
-   Báo Chính phủ
-   TTXVN
-   Tuổi Trẻ
-   Thanh Niên
-   Người Lao Động
-   Kinh tế Sài Gòn

Recommended data:

-   Company news
-   Industry news
-   Government policy
-   Macroeconomic news

Avoid:

-   Opinion articles
-   Market commentary
-   Investment recommendations

------------------------------------------------------------------------

## Tier 3 -- Financial News Websites

Examples:

-   CafeF
-   Vietstock
-   NDH

Useful sections:

-   Company announcements
-   Financial reports
-   Corporate events

Avoid:

-   Analyst recommendations
-   Buy/Sell reports
-   Editorial opinions

------------------------------------------------------------------------

# Data Categories

## Company Events

Priority:

-   HOSE
-   HNX
-   Company IR

Examples:

-   Earnings release
-   Dividend
-   Stock split
-   Rights issue
-   Bond issuance
-   M&A
-   Executive changes

------------------------------------------------------------------------

## Financial Reports

Sources:

-   Company IR
-   HOSE
-   HNX

Do not rely on third-party copies if original filings are available.

------------------------------------------------------------------------

## Macroeconomic Data

Sources:

-   State Bank of Vietnam
-   Ministry of Finance
-   General Statistics Office
-   Government Portal
-   Ministry of Industry and Trade

Examples:

-   CPI
-   GDP
-   Interest rates
-   Exchange rates
-   Import/Export
-   Inflation

------------------------------------------------------------------------

## International News

Useful sources:

-   Reuters
-   Bloomberg
-   IMF
-   World Bank
-   Federal Reserve

------------------------------------------------------------------------

# Sources to Exclude

Do NOT train sentiment models using:

-   Facebook
-   TikTok
-   Telegram
-   YouTube
-   Stock forums
-   Investor chat rooms
-   Personal blogs
-   Broker recommendations
-   Market prediction articles

Reason:

These contain human opinions and introduce significant bias.

------------------------------------------------------------------------

# Recommended Crawling Architecture

``` text
                 Scheduler
                     │
     ┌───────────────┼────────────────┐
     │               │                │
 HOSE/HNX       Company IR        Macro
     │               │                │
     ├───────────────┼────────────────┤
                     │
              Raw HTML/PDF/XML
                     │
              Metadata Extract
                     │
      Title
      Publish Time
      Company Code
      Category
      URL
      Raw Content
                     │
            NLP Processing
                     │
    PhoBERT / FinBERT / NER
                     │
 Event Extraction + Sentiment + Embedding
                     │
             Feature Store
                     │
        Volatility Prediction Model
```

------------------------------------------------------------------------

# Metadata Schema

For every crawled document store:

-   document_id
-   source
-   url
-   publish_time
-   crawl_time
-   company_code
-   company_name
-   title
-   raw_text
-   language
-   category
-   event_type
-   attachment_urls
-   checksum

------------------------------------------------------------------------

# Best Practices

-   Crawl original sources before secondary sources.
-   Preserve raw HTML/PDF for reproducibility.
-   Keep timestamps in UTC.
-   Version datasets.
-   Deduplicate by checksum or URL.
-   Separate raw, cleaned, and feature layers.
-   Never mix analyst opinions with objective events in the same
    training dataset.
