## How Safety Agreement Is Calculated

The **safety agreement percentage** is calculated separately for each test run:

$$
\text{Safety agreement (\%)} =
\frac{\text{largest group of correct peers that delivered the same value}}
{\text{total number of correct peers that delivered a value}}
\times 100
$$

### Example

Suppose there are 90 correct peers:

- 80 correct peers complete BRB delivery.
- 64 deliver value `0`.
- 16 deliver value `1`.
- The largest agreeing group contains 64 peers.

Therefore:

$$
\text{Safety agreement} = \frac{64}{80} \times 100 = 80\%
$$

The denominator is 80 because only correct peers that completed BRB delivery are considered. The 10 correct peers that did not deliver are excluded.

### Interpreting the Result

- **100% agreement:** All correct peers that delivered chose the same value.
- **80% agreement:** The largest agreeing group contained 80% of the correct peers that delivered.
- **50% agreement:** The delivered correct peers may have been divided equally between two values.

For each Byzantine count \(t\), the calculation is performed for every test run. The graph shows the **mean safety agreement percentage** across those runs. The error bars show the **95% confidence interval** around the mean.

> **Important:** This metric measures agreement, but it does not measure whether the delivered value was the sender's intended value. Even 100% agreement could mean that all correct peers agreed on an incorrect value.
