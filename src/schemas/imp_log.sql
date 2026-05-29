CREATE TABLE imp_log
(
    bid_id              String,
    timestamp_raw       String,
    ts                  DateTime64(3) MATERIALIZED
        parseDateTime64BestEffort(
            concat(
                substring(timestamp_raw,  1, 4), '-',   -- YYYY
                substring(timestamp_raw,  5, 2), '-',   -- MM
                substring(timestamp_raw,  7, 2), ' ',   -- DD
                substring(timestamp_raw,  9, 2), ':',   -- HH
                substring(timestamp_raw, 11, 2), ':',   -- MM
                substring(timestamp_raw, 13, 2), '.',   -- SS
                substring(timestamp_raw, 15, 3)         -- mmm
            ), 3),
    log_type            UInt8,                          -- 1 = impression
    ipinyou_id          Nullable(String),
    user_agent          Nullable(String),
    ip                  Nullable(String),
    region_id           Nullable(UInt32),
    city_id             Nullable(UInt32),
    ad_exchange         UInt8 DEFAULT 0,
    domain              Nullable(String),
    url                 Nullable(String),
    anonymous_url       Nullable(String),
    ad_slot_id          String,
    ad_slot_width       Nullable(UInt32),
    ad_slot_height      Nullable(UInt32),
    ad_slot_visibility  LowCardinality(Nullable(String)),
    ad_slot_format      LowCardinality(Nullable(String)),
    ad_slot_floor_price Nullable(UInt32),
    creative_id         Nullable(String),
    bidding_price       Nullable(UInt32),
    paying_price        Nullable(UInt32),               -- actual clearing price paid by DSP
    landing_page_url    Nullable(String),
    advertiser_id       Nullable(UInt32),
    user_profile_ids    Nullable(String),
    platform            String,
    browser             String
)
ENGINE = MergeTree()
ORDER BY ts;
