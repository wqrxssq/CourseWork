CREATE TABLE bid_log
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
    ipinyou_id          Nullable(String),
    user_agent          Nullable(String),
    ip                  Nullable(String),
    region_id           Nullable(UInt32),
    city_id             Nullable(UInt32),
    ad_exchange         UInt8 DEFAULT 0,                -- 0 = Unknown; 1-6 = known exchanges
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
    advertiser_id       Nullable(UInt32),
    user_profile_ids    Nullable(String),
    platform            String,                         -- derived from user_agent by enricher
    browser             String                          -- derived from user_agent by enricher
)
ENGINE = MergeTree()
ORDER BY ts;
