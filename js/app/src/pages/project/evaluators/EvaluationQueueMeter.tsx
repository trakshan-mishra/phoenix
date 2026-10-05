import { css } from "@emotion/react";

import { Flex, Text } from "@phoenix/components";
import { intFormatter } from "@phoenix/utils/numberFormatUtils";

export type EvaluationQueueMeterSegment = {
  /** Stable key, e.g. the evaluation target. */
  id: string;
  /** Lowercase noun shown in the legend, e.g. "spans". */
  label: string;
  count: number;
  /** A CSS color, e.g. a categorical chart color. */
  color: string;
};

const trackCSS = css`
  display: flex;
  flex-direction: row;
  width: 100%;
  height: var(--global-dimension-size-75);
  border-radius: 3px;
  overflow: hidden;
  background-color: var(--global-color-gray-300);
`;

const swatchCSS = css`
  width: var(--global-dimension-size-100);
  height: var(--global-dimension-size-100);
  border-radius: 2px;
  flex: none;
`;

/**
 * How full the evaluation queue is, as one bar against its limit with a
 * section per kind of evaluation, and a legend naming each kind's count.
 */
export function EvaluationQueueMeter({
  segments,
  limit,
  width = "300px",
}: {
  segments: ReadonlyArray<EvaluationQueueMeterSegment>;
  limit: number;
  width?: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  // A queue can briefly hold more than its limit; the bar never overflows.
  const scale = Math.max(limit, total, 1);
  const description = segments
    .map((segment) => `${segment.label} ${intFormatter(segment.count)}`)
    .join(", ");
  return (
    <Flex direction="column" gap="size-50" width={width}>
      <div
        css={trackCSS}
        role="img"
        aria-label={`${intFormatter(total)} of ${intFormatter(limit)} queued: ${description}`}
      >
        {segments.map((segment) => (
          <div
            key={segment.id}
            style={{
              width: `${(segment.count / scale) * 100}%`,
              // A kind with any work queued stays visible against a large limit.
              minWidth: segment.count > 0 ? "2px" : undefined,
              backgroundColor: segment.color,
            }}
          />
        ))}
      </div>
      <Flex direction="row" gap="size-150" wrap="nowrap" aria-hidden>
        {segments.length === 0 ? (
          // Keeps the legend's line while the counts load.
          <Text size="XS">{"\u00a0"}</Text>
        ) : null}
        {segments.map((segment) => (
          <Flex
            key={segment.id}
            direction="row"
            gap="size-50"
            alignItems="center"
          >
            <span css={swatchCSS} style={{ backgroundColor: segment.color }} />
            <Text size="XS" color="text-700">
              {`${segment.label} ${intFormatter(segment.count)}`}
            </Text>
          </Flex>
        ))}
      </Flex>
    </Flex>
  );
}
