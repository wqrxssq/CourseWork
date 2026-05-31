const { buildSource } = require('libs/dataset/v2');

module.exports = {
    rtbSource: buildSource({
        datasetId: Editor.getId('dataset'),
        columns: ['bids', 'imps', 'clicks', 'convs'],
    }),
};