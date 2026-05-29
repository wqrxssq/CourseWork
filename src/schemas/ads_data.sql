CREATE TABLE ads_data
ENGINE = MergeTree()
ORDER BY advertiser_id
AS
SELECT
    bid_id,
    ts,
    timestamp_raw,
    ipinyou_id,
    user_agent,
    ip,
    region_id,
    city_id,
    ad_exchange,
    domain,
    url,
    anonymous_url,
    ad_slot_id,
    ad_slot_width,
    ad_slot_height,
    ad_slot_visibility,
    ad_slot_format,
    ad_slot_floor_price,
    creative_id,
    bidding_price,
    coalesce(advertiser_id, 0) AS advertiser_id,   -- NULL -> 0 (Unknown advertiser)
    user_profile_ids,
    platform,
    browser,
    paying_price,
    landing_page_url,
    is_win,
    is_clicked,
    is_conversion
FROM joined_ads_data;
