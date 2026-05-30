CREATE TABLE ipinyou_db.regions
(
    region_id   UInt32,
    region_name String
)
ENGINE = MergeTree
ORDER BY region_id;
