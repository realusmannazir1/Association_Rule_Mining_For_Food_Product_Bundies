# Viva preparation: DS-A38

Use these as prompts to explain the implementation in your own words. Replace every demonstration result with the result from the Dunnhumby data you actually process.

## Core questions

**What problem does this project solve?**  
It finds products that co-occur in grocery baskets and ranks the associations as possible cross-selling or bundle hypotheses.

**What is a transaction in this project?**  
One shopping basket represented as the set of distinct product descriptions purchased in it. For the assigned data, explain exactly how transaction rows are grouped and how product IDs are mapped to descriptions.

**What is support?**  
The fraction of all baskets containing the itemset. It indicates how common the pattern is.

**What is confidence? Why is it insufficient?**  
For X -> Y, confidence is support(X and Y) divided by support(X). It is directional but ignores how common Y is overall. In the demonstration sample, eggs -> butter has confidence about 0.67, but butter is already in 65% of baskets, so lift is only about 1.03.

**What is lift?**  
Confidence(X -> Y) divided by support(Y). A lift near 1 means the consequent occurs about as often as expected from its baseline frequency; above 1 is positive association and below 1 is negative association.

**How does Apriori work?**  
It expands candidate itemsets by size. If an itemset is infrequent, all its supersets can be pruned because a superset cannot have greater support.

**How does FP-Growth work?**  
It compresses transactions into a frequent-pattern tree and mines conditional pattern bases/trees without explicit candidate generation.

**Why compare them?**  
They solve the same frequent-itemset problem using different search strategies. On the same transactions and thresholds, their frequent itemsets should match; runtime and memory vary with data shape and scale.

## Demonstration results (not final Dunnhumby findings)

- 20 baskets, 4 products, average basket size 2.55.
- At minimum support 0.05, minimum confidence 0.30 and minimum lift 1.0: both algorithms found 15 itemsets and 5 rules.
- Strongest observed lift was about 1.10 for bread and eggs -> butter; this is a weak hypothesis on this tiny sample, not a reliable recommendation.
- The run time difference is too small and the sample too tiny for any scalability conclusion.

## Be ready to explain

- The exact source files and period downloaded from Dunnhumby, the join keys, product description mapping, basket definition and rows removed.
- Missing IDs, duplicates, repeated products, whether quantities were retained or reduced to presence/absence, and any sampling choices.
- Why you selected thresholds and how changing support affects the number of itemsets/rules.
- One final rule using its support, confidence, lift and plain-language interpretation.
- Why co-occurrence does not imply causation, plus effects such as promotions, seasonality and stock availability.
- The limitations of your analysis and what you would validate before a retailer deployed a bundle.

## Academic integrity note

The course brief says the work must be independently understood and external or AI assistance disclosed as required by course policy. Review and adapt the project yourself, verify the data and results, and follow your instructor's citation rules.
