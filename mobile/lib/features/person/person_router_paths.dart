/// The home of a person of the church trust model. Until the older accounts go (roadmap S5) the
/// person screens have their own addresses next to the older ones.
const personHome = '/member';
const personVouches = '/member/vouches';
const personNotifications = '/member/notifications';

/// A vouch link opens here. The token is handed over in the route's in-memory `extra`, so it is
/// never part of an address that a router log or observer could record.
const vouchLinkPath = '/vouch';
const personGroupRequests = '/member/group-requests';
