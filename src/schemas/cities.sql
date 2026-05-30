CREATE TABLE ipinyou_db.cities
(
    city_id   UInt32,
    city_name String
)
ENGINE = MergeTree
ORDER BY city_id;
