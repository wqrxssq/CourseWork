const Dataset = require('libs/dataset/v2');
const data = Dataset.getDatasetRows({datasetName: 'rtbSource'});

function toNumber(value) {
    if (value === true) return 1;
    if (value === false || value == null || value === '') return 0;

    const normalized = String(value)
        .trim()
        .replace(/\s+/g, '')
        .replace(',', '.');

    const num = Number(normalized);
    return Number.isFinite(num) ? num : 0;
}

function fmtInt(value) {
    return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function fmtPct(value, opts = {}) {
    if (!Number.isFinite(value)) return '—';

    const pct = value * 100;

    let digits;
    if (opts.digits != null) {
        digits = opts.digits;
    } else if (pct >= 10) {
        digits = 1;
    } else if (pct >= 1) {
        digits = 2;
    } else {
        digits = 3;
    }

    return `${pct.toFixed(digits).replace('.', ',')}%`;
}

console.log(data);

const actionParams = Editor.getParams();
console.log(actionParams);

const dateInterval = actionParams?.ts_truncated;
let dateFrom = null;
let dateTo = null;

if (dateInterval) {
    const resolved = Editor.resolveInterval(dateInterval);
    if (resolved && resolved.from && resolved.to) {
        dateFrom = new Date(resolved.from);
        dateTo = new Date(resolved.to);
    }
}

console.log('dateFrom:', dateFrom);
console.log('dateTo:', dateTo);

function cleanParams(arr) {
    if (!arr || !Array.isArray(arr)) return [];
    return arr.filter(v => v != null && String(v).trim() !== '');
}

const selectedPlatform = cleanParams(actionParams?.platform);
console.log(selectedPlatform);

const selectedBrowser = cleanParams(actionParams?.browser);
console.log(selectedBrowser);

const selectedAdvertiser = cleanParams(actionParams?.advertiser_name);
console.log(selectedAdvertiser);

const filteredData = data.filter(row => {
    const platformMatch = selectedPlatform.length === 0 || selectedPlatform.includes(String(row?.platform));
    const browserMatch = selectedBrowser.length === 0 || selectedBrowser.includes(String(row?.browser));
    const advertiserMatch = selectedAdvertiser.length === 0 || selectedAdvertiser.includes(String(row?.advertiser_name));
    
    let dateMatch = true;
    if (dateFrom && dateTo && row?.ts_truncated) {
        const rowDate = new Date(row.ts_truncated);
        if (!isNaN(rowDate.getTime())) {
            dateMatch = rowDate >= dateFrom && rowDate <= dateTo;
        }
    }
    
    return platformMatch && browserMatch && advertiserMatch && dateMatch;
});

let bids = 0;
let imps = 0;
let clicks = 0;
let convs = 0;

for (const row of filteredData) {
    bids += toNumber(row?.bids);
    imps += toNumber(row?.imps);
    clicks += toNumber(row?.clicks);
    convs += toNumber(row?.convs);
}

const rows = filteredData;

const winRatio = bids ? imps / bids : 0;
const ctr = imps ? clicks / imps : 0;
const cvr = clicks ? convs / clicks : 0;
const fullConv = bids ? convs / bids : 0;

const labels = Editor.getLang() === 'ru'
    ? {
        title: 'RTB-воронка',
        subtitle: 'bid → impression → click → conversion',
        bids: 'Ставки',
        imps: 'Показы',
        clicks: 'Клики',
        convs: 'Конверсии',
        base: 'База',
        winRatio: 'win ratio',
        ctr: 'CTR',
        cvr: 'CVR',
        fromPrev: 'от предыдущего этапа',
        fromBids: 'от ставок',
        rows: 'Строк',
    }
    : {
        title: 'RTB funnel',
        subtitle: 'bid → impression → click → conversion',
        bids: 'Bids',
        imps: 'Impressions',
        clicks: 'Clicks',
        convs: 'Conversions',
        base: 'Base',
        winRatio: 'win ratio',
        ctr: 'CTR',
        cvr: 'CVR',
        fromPrev: 'from previous stage',
        fromBids: 'from bids',
        rows: 'Rows',
    };

const chartData = {
    labels,
    rowsCount: rows.length,
    summary: [
        { label: labels.bids, value: bids, meta: labels.base },
        { label: labels.imps, value: imps, meta: `${labels.winRatio}: ${fmtPct(winRatio)}` },
        { label: labels.clicks, value: clicks, meta: `${labels.ctr}: ${fmtPct(ctr)}` },
        { label: labels.convs, value: convs, meta: `${labels.cvr}: ${fmtPct(cvr)}` },
    ],
    stages: [
        { label: labels.bids, value: bids, rate: 1, rateLabel: labels.base },
        { label: labels.imps, value: imps, rate: winRatio, rateLabel: labels.fromPrev },
        { label: labels.clicks, value: clicks, rate: ctr, rateLabel: labels.fromPrev },
        { label: labels.convs, value: convs, rate: cvr, rateLabel: labels.fromPrev },
    ],
    totals: {
        bids,
        imps,
        clicks,
        convs,
        winRatio,
        ctr,
        cvr,
        fullConv,
    },
};

module.exports = {
    render: Editor.wrapFn({
        fn: function (options, chartData) {
            const { width, height } = options;
            const { labels, summary, stages, rowsCount, totals } = chartData;

            function esc(value) {
                return String(value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#39;');
            }

            function fmtInt(value) {
                return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
            }

            function fmtPct(value, opts = {}) {
                if (!Number.isFinite(value)) return '—';

                const pct = value * 100;

                let digits;
                if (opts.digits != null) {
                    digits = opts.digits;
                } else if (pct >= 10) {
                    digits = 1;
                } else if (pct >= 1) {
                    digits = 2;
                } else {
                    digits = 3;
                }

                return `${pct.toFixed(digits).replace('.', ',')}%`;
            }


            const summaryHtml = summary.map((item) => `
                <div style="
                    box-sizing: border-box;
                    padding: 14px 14px 12px;
                    border-radius: 16px;
                    background: rgba(0, 0, 0, 0.04);
                    border: 1px solid rgba(0, 0, 0, 0.06);
                    min-width: 0;
                ">
                    <div style="font-size: 12px; opacity: 0.72; margin-bottom: 6px;">
                        ${esc(item.label)}
                    </div>
                    <div style="font-size: 20px; font-weight: 700; line-height: 1.1;">
                        ${fmtInt(item.value)}
                    </div>
                    <div style="font-size: 12px; opacity: 0.72; margin-top: 6px;">
                        ${esc(item.meta)}
                    </div>
                </div>
            `).join('');

            const stageHtml = stages.map((stage, idx) => {
                const prev = idx === 0 ? null : stages[idx - 1].value;
                const prevRate = idx === 0 ? 1 : (prev ? stage.value / prev : 0);
                const shareOfBids = totals.bids ? stage.value / totals.bids : 0;

                // степень < 1 усиливает различия (особенно в середине)
                const widthPct = idx === 0
                    ? 100
                    : Math.max(4, Math.round(100 * Math.pow(shareOfBids, 0.1)));

                return `
                    <div style="display: grid; grid-template-columns: 130px 1fr; gap: 12px; align-items: center;">
                        <div style="font-size: 14px; font-weight: 600; opacity: 0.92;">
                            ${esc(stage.label)}
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 6px; min-width: 0;">
                            <div style="
                                position: relative;
                                width: ${widthPct}%;
                                min-width: 100px;
                                max-width: 100%;
                                height: 44px;
                                margin: 0 auto;
                                border-radius: 14px;
                                overflow: hidden;
                                background: rgba(79, 70, 229, 0.12);
                                clip-path: polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%);
                            ">
                                <div style="
                                    position: absolute;
                                    inset: 0;
                                    background: linear-gradient(90deg, rgba(79, 70, 229, 0.92), rgba(99, 102, 241, 0.62));
                                "></div>
                                <div style="
                                    position: absolute;
                                    inset: 0;
                                    display: flex;
                                    align-items: center;
                                    justify-content: space-between;
                                    gap: 10px;
                                    padding: 0 14px;
                                    color: white;
                                    font-size: 14px;
                                    font-weight: 700;
                                ">
                                    <span>${fmtInt(stage.value)}</span>
                                    <span>${idx === 0 ? '100%' : fmtPct(stage.value / totals.bids)}</span>
                                </div>
                            </div>
                            <div style="font-size: 12px; opacity: 0.72; text-align: center;">
                                ${idx === 0
                                    ? `${labels.base}`
                                    : `${fmtPct(prevRate)} ${stage.rateLabel}`}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            return Editor.generateHtml(`
                <div style="
                    box-sizing: border-box;
                    width: ${width}px;
                    height: ${height}px;
                    padding: 16px 18px;
                    color: inherit;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    overflow: auto;
                ">
                    <div style="display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; margin-bottom: 14px;">
                        <div>
                            <div style="font-size: 22px; font-weight: 800; line-height: 1.1;">
                                ${esc(labels.title)}
                            </div>
                            <div style="font-size: 12px; opacity: 0.72; margin-top: 4px;">
                                ${esc(labels.subtitle)}
                            </div>
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px;">
                        ${summaryHtml}
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 14px;">
                        ${stageHtml}
                    </div>
                </div>
            `);
        },
        args: [chartData],
    }),
};
