import { useEffect, useState } from 'react';
import { subscribeSecurityFeed, FeedState, SecurityEvent } from '../api/securityFeed';

export const useSecurityFeed = (): FeedState & { latest: SecurityEvent | null } => {
  const [feed, setFeed] = useState<FeedState>({ connected: false, events: [], revision: 0 });

  useEffect(() => subscribeSecurityFeed(setFeed), []);

  return { ...feed, latest: feed.events[0] ?? null };
};
