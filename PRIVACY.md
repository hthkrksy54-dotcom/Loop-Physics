<p><img src="docs/developed-with-youtube-sentence-case-dark.png" alt="Developed with YouTube" width="210"></p>

# Privacy Policy – ytauto (Quiet Thoughts, Loop Physics)

_Last updated: 16 October 2026_

ytauto is a private, internal automation tool operated by one person, the owner of the YouTube channels
[Quiet Thoughts](https://www.youtube.com/@quietthoughts-20) and [Loop Physics](https://www.youtube.com/@LoopPhysics-420).
It is not offered to the public and has exactly one user: the channel owner.

## Use of YouTube API Services

ytauto uses the **YouTube API Services** to:

- upload the owner's own videos to the owner's own channels and set their thumbnails and captions;
- update the title, description and tags of the owner's own videos and sort them into the owner's own playlists;
- set the banner, description and keywords of the owner's own channels;
- read public metadata of popular public Shorts (`search.list`, `videos.list`) to compute aggregate trend statistics
  for the owner's own content planning (see below).

By using ytauto you agree to be bound by the [YouTube Terms of Service](https://www.youtube.com/t/terms).

Google's privacy practices apply to all data processed through YouTube API Services:
**[Google Privacy Policy](https://policies.google.com/privacy)**.

## What data is accessed

- The OAuth 2.0 authorization granted by the channel owner for each of the owner's channels
  (scope `https://www.googleapis.com/auth/youtube.force-ssl`).
- The owner's own channel ID and title (to confirm the correct channel is connected), and the IDs, titles,
  durations and view counts of the owner's own uploaded videos (to match each produced video to its upload).
- For the daily trend check: public metadata (title, tags, view count, duration) of popular public Shorts returned
  by YouTube search. This data is processed **in memory during a single run** to compute aggregate statistics
  (keyword frequencies, typical length, share of themes). The individual records are **not stored**.

ytauto does **not** access, collect or store any data about viewers, subscribers, commenters or any other YouTube
users. It does not read analytics, comments or private videos of anyone.

## How data is used, stored and shared

- OAuth refresh tokens are stored encrypted – as GitHub Actions secrets, or as encrypted files in this repository
  whose key is a GitHub Actions secret – and are used only for the purposes listed above.
- Video metadata (title, description, tags) is created by ytauto itself and stored in this repository, together
  with the IDs of the owner's own uploaded videos.
- Only aggregate trend statistics derived from public data are stored (no titles, IDs or statistics of
  third-party videos).
- No data is sold, shared with third parties, or used for advertising.
- ytauto does not use cookies or tracking technologies.

## Retention and deletion

- Refresh tokens are kept only while the tool is in use. Deleting the secret or the encrypted file removes them.
- Public data from YouTube search is discarded at the end of each run; aggregate statistics are replaced daily.
- IDs of the owner's own videos are kept while the owner uses the tool and are deleted on request.
- To request deletion of any data or ask questions, open an issue at
  <https://github.com/hthkrksy54-dotcom/Yt/issues>.

## Revoking access

Access can be revoked at any time on the Google security settings page:
<https://security.google.com/settings/security/permissions>.

## Instagram

ytauto also posts short videos as Reels and Stories to the owner's own Instagram accounts (@quiet_thoughts_yt,
@loop_physics) using the Instagram API with Instagram Login, and reads the statistics of these accounts' own posts
(views, reach, likes, saves, shares) to see which videos work best. Access tokens are stored encrypted in this
repository and can only be decrypted with a key kept as a GitHub Actions secret. No data about other Instagram
users is accessed. Access can be removed at any time in Instagram → Settings → Apps and websites.

## Contact

<https://github.com/hthkrksy54-dotcom/Yt/issues>
