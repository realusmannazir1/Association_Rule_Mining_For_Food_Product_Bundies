# Association Rule Mining for Food Product Bundles (DS-A38)

**Student:** Muhammad Usman Nazir  
**Registration:** 24PWDSC0178

This project prepares baskets, explores product frequency and basket sizes, mines frequent itemsets using Apriori and FP-Growth, compares their outputs and runtime, and ranks association rules using support, confidence, and lift. Confidence alone can be misleading: a popular consequent can have high confidence even when it is no more likely after the antecedent than its ordinary basket frequency. Lift compares those probabilities; lift above 1 indicates positive association.

## Dataset and provenance

The included `data/groceries.csv` is a small, 20-row illustrative example for checking the workflow. Its provenance is not Dunnhumby, so do not describe its results as Dunnhumby findings. For the assigned dataset, download **The Complete Journey** from the [official Dunnhumby Source Files page](https://www.dunnhumby.com/source-files/). It represents two years of purchases from 2,500 frequent-shopping households and has multiple related tables. Record the exact downloaded file names, download date, selected time period/sample, columns, and any license/usage conditions in the report.

For mining, first join the transaction and product tables using the dataset's transaction and product keys, map product IDs to readable product descriptions, then aggregate to one row per `(basket_id, product_name)`. Save as a CSV with headers `basket_id,product_name`. The loader also supports the included wide format (`transaction_id` followed by item columns).

Official source: https://www.dunnhumby.com/source-files/ (accessed 2026-11-24)

## Run

On Windows, double-click `Run_Project.bat` to open the Basket Insights desktop app. The dashboard includes collapsible navigation, a searchable and sortable rule explorer, frequent itemsets, an algorithm comparison, a chart studio, dataset settings, and report exports. Choose a CSV and thresholds, then select **Run analysis**. Exports include a multi-sheet Excel workbook, filtered rules CSV, and a PDF report. Results and charts are also saved in `output/`. If dependencies are missing, the launcher installs them from `requirements.txt`.

```powershell
python -m pip install -r requirements.txt
python main.py --data data/groceries.csv --support 0.10 --confidence 0.30 --lift 1.0
```

For a prepared Dunnhumby basket-item CSV:

```powershell
python main.py --data data/dunnhumby_basket_items.csv --support 0.01 --confidence 0.20 --lift 1.1
```

Thresholds should be selected after inspecting the dataset size and item frequency. If the full dataset is large, start with a documented sample/time period and a higher support threshold. Keep the same thresholds for both algorithms. Apriori and FP-Growth should return equivalent frequent itemsets/rules under equal settings; runtime differences depend on the data and hardware, and a tiny sample is not a meaningful speed benchmark.

The pipeline outputs dataset summaries, EDA plots, frequent itemsets and rule tables for each algorithm, plus a combined ranked-rule file and visualizations in `output/`.

## Metric interpretation

- **Support**: fraction of all baskets containing the entire itemset.
- **Confidence** for X -> Y: fraction of baskets containing X that also contain Y. It is directional, but does not account for Y's baseline popularity.
- **Lift**: confidence(X -> Y) / support(Y). Lift = 1 means no association beyond independence; >1 positive association; <1 negative association.
- **Rule ranking**: inspect lift together with support and confidence. Very high lift from a rare pair may be unstable or have little business reach. A bundle suggestion should have adequate support, lift meaningfully above 1, and products that make commercial sense.

## Limitations and academic integrity

Association is not causation. Baskets reflect promotions, seasonality, household behavior and data coverage; these factors are not controlled in simple association mining. The included sample is too small for reliable commercial conclusions. Replace it with the assigned source data, independently inspect the merges and thresholds, explain each code section in your own words, and cite any AI assistance according to course policy. The report and notebook are working drafts until actual Dunnhumby data have been processed and the results updated.
