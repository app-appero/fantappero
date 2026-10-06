"""Directory invite status after a member leaves the league."""

from database.enums import NamedInviteStatus
from leagues.named_invite_service import directory_invite_status


def test_stale_accepted_invite_does_not_block_a_new_one() -> None:
    assert directory_invite_status(None) is None
    assert directory_invite_status(NamedInviteStatus.ACCEPTED) is None
    assert directory_invite_status(NamedInviteStatus.PENDING) == "pending"
    assert directory_invite_status(NamedInviteStatus.REVOKED) == "revoked"
    assert directory_invite_status(NamedInviteStatus.DECLINED) == "declined"
    assert directory_invite_status(NamedInviteStatus.EXPIRED) == "expired"
