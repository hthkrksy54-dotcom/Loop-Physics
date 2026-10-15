<p><img src="docs/developed-with-youtube-sentence-case-dark.png" alt="Developed with YouTube" width="210"></p>

# Privacy Policy – ytauto (Quiet Thoughts)

_Last updated: 15 October 2026_

ytauto is a private, internal automation tool operated by the owner of the YouTube channel
[Quiet Thoughts](https://www.youtube.com/@quietthoughts-20). It is not offered to the public and has exactly
one user: the channel owner.

## Use of YouTube API Services

ytauto uses the **YouTube API Services** to upload videos, set thumbnails and add captions to the owner's own
YouTube channel. By using ytauto you agree to be bound by the
[YouTube Terms of Service](https://www.youtube.com/t/terms).

Google's privacy practices apply to all data processed through YouTube API Services:
**[Google Privacy Policy](https://policies.google.com/privacy)**.

## What data is accessed

- The OAuth 2.0 authorization granted by the channel owner (scope `https://www.googleapis.com/auth/youtube.force-ssl`).
- The owner's own channel ID and title (to confirm the correct channel is connected).

ytauto does **not** access, collect or store any data about viewers, subscribers, commenters or any other YouTube
users. It does not read analytics, comments or private videos.

## How data is used, stored and shared

- The OAuth refresh token is stored encrypted as a GitHub Actions secret and is used only to upload the owner's
  own videos, thumbnails and captions to the owner's own channel.
- Video metadata (title, description, tags) is created by ytauto itself and stored in this repository.
- No data is sold, shared with third parties, or used for advertising.
- ytauto does not use cookies or tracking technologies.

## Retention and deletion

- The refresh token is kept only while the tool is in use. Deleting the GitHub secret removes it immediately.
- No other personal data is stored. Data obtained from YouTube API Services (channel ID and title) is not
  persisted beyond a single run.
- To request deletion of any data or ask questions, open an issue at
  <https://github.com/hthkrksy54-dotcom/Yt/issues>.

## Revoking access

Access can be revoked at any time on the Google security settings page:
<https://security.google.com/settings/security/permissions>.

## Instagram

ytauto also posts the same short videos as Reels to the owner's own Instagram account
(@quiet_thoughts_yt) using the Instagram API with Instagram Login (permissions `instagram_business_basic`
and `instagram_business_content_publish`). The access token is stored encrypted in this repository and can
only be decrypted with a key kept as a GitHub Actions secret. No data about other Instagram users is
accessed. Access can be removed at any time in Instagram → Settings → Apps and websites.

## Contact

<https://github.com/hthkrksy54-dotcom/Yt/issues>
