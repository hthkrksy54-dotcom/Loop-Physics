# ytauto – YouTube API upload walkthrough

For the YouTube API Services compliance review · recorded on 27 October 2026 · contact: samuel.moedl@gmx.de

**Screencast (2 min, English captions):** [8_api_upload_walkthrough.mp4](8_api_upload_walkthrough.mp4)

## What the tool is

**ytauto** is a private, internal tool of a single channel owner (Samuel Mödl). It renders original videos and publishes
them to the owner's own YouTube channels. Nobody else signs in, and the tool stores no viewer data. Its source code
is public: https://github.com/hthkrksy54-dotcom/Yt

The active channel is **[Loop Physics](https://www.youtube.com/@LoopPhysics-420)**. It posts generated physics
simulations that the tool renders itself, with public-domain melodies the simulation plays note by note.
The other two channels (Quiet Thoughts, Real Numbers) are paused as of 27 October 2026.

## How a video is uploaded (step by step)

1. **Schedule.** A GitHub Actions workflow ([sims.yml](https://github.com/hthkrksy54-dotcom/Yt/blob/55313c1/.github/workflows/sims.yml#L1-L13)) runs the tool
   three times a day. Each run renders one new simulation video (MP4, 1080×1920, about 60–80 s).
2. **Authorization.** The owner authorized the tool once with Google OAuth 2.0 on his own account
   (scope `https://www.googleapis.com/auth/youtube`). The refresh token is stored encrypted. Each run exchanges it for
   a short-lived access token ([youtube.py, `access_token_from`](https://github.com/hthkrksy54-dotcom/Yt/blob/55313c1/ytauto/youtube.py#L30-L44)).
   `channels.list(mine=true)` confirms that the token belongs to the expected channel before anything is changed.
3. **Metadata.** The tool writes the title, description, tags, category and language for the video and sets
   `privacyStatus: public` and `selfDeclaredMadeForKids: false`
   ([simchannel.py](https://github.com/hthkrksy54-dotcom/Yt/blob/55313c1/ytauto/simchannel.py#L801-L812)).
4. **Upload.** `videos.insert` (`part=snippet,status`) uploads the file as a resumable upload in chunks. YouTube
   returns the new video id ([youtube.py, `upload_video`](https://github.com/hthkrksy54-dotcom/Yt/blob/55313c1/ytauto/youtube.py#L47-L97)).
5. **Check.** `videos.list(part=snippet,status)` reads the video back to confirm its title and visibility.

Other calls on the owner's own content:
- `videos.update` gives videos the owner uploads by hand their prepared title, description and tags.
- `playlistItems.insert` sorts videos into the channel's own playlists.
- `channels.update` and `channelBanners.insert` maintain the channel's own description and banner.
- A daily trend check uses `search.list` and `videos.list`. Its public data is only aggregated in memory, never stored.

## Real run on 27 October 2026

Workflow run [40566689378](https://github.com/hthkrksy54-dotcom/Yt/actions/runs/40566689378) published the simulation "Tower #3" through exactly this
path (command `python -m ytauto sims --youtube demo`, which calls the same `upload_video` function as the scheduled
runs and logs every step):

```
$ python -m ytauto sims --youtube demo        # GitHub Actions run 40566689378, 2026-10-27 19:10 UTC
== Step 1: OAuth 2.0 – exchange the channel owner's stored refresh token for an access token
   access token received (scope: https://www.googleapis.com/auth/youtube; never printed or stored)
== Step 2: channels.list(mine=true) – the token belongs to 'Loop Physics' (UCE41z98kd_7QRN4ph-ecaUQ)
== Step 3: the video to publish – rendered by this tool on 2026-10-25T22:41 UTC (tower_drop, 66.3 s, 157.3 MB): https://github.com/hthkrksy54-dotcom/Yt/releases/download/sims-20261025-tower_drop-2/loop-physics-20261025-tower_drop-2.mp4
== Step 4: videos.insert (part=snippet,status, resumable upload) with this request body:
{
  "snippet": {
    "title": "Tower #3: Can the ball fall through 110 floors?",
    "description": "Can the ball fall through 110 floors? Name the song before the finale.\n\nTower #3: a ball bounces down a spinning tower of 110 floors made of glossy beads. Every bounce plays the next note of a famous melody, every floor it drops through bursts with a crack – faster every ten floors, and the last twelve are smashed in fire mode. Every episode the tower gets five floors taller. Everything is simulated in 3D, nothing is animated.\n\n◀ Previous episode: https://youtube.com/shorts/NfesOyi_x70\n\n🎵 The melody is a public-domain classic, played note by note by the simulation – no recording is used.\n\n💬 Which song is this? 🎵 Write it in the comments!\n\n🔔 Subscribe so you don't miss Tower #4.\n\n#satisfying #physics #simulation #shorts",
    "tags": [
      "satisfying",
      "oddly satisfying",
      "physics simulation",
      "bouncing ball",
      "satisfying video",
      "simulation",
      "relaxing",
      "asmr",
      "classical music",
      "a famous melody",
      "bouncingball",
      "physicssimulation"
    ],
    "categoryId": "28",
    "defaultLanguage": "en"
  },
  "status": {
    "privacyStatus": "public",
    "selfDeclaredMadeForKids": false
  }
}
   upload complete – YouTube returned the video id XNDvJNetw78
== Step 5: end result, read back with videos.list(part=snippet,status):
{
  "id": "XNDvJNetw78",
  "title": "Tower #3: Can the ball fall through 110 floors?",
  "channelTitle": "Loop Physics",
  "status": {
    "uploadStatus": "uploaded",
    "privacyStatus": "public",
    "license": "youtube",
    "embeddable": true,
    "publicStatsViewable": true,
    "madeForKids": false,
    "selfDeclaredMadeForKids": false
  }
}
   requested privacyStatus: public – privacyStatus now: public
   https://youtube.com/shorts/XNDvJNetw78
```

## End result

Video **[XNDvJNetw78](https://www.youtube.com/shorts/XNDvJNetw78)** – "Tower #3: Can the ball fall through 110
floors?" – is live and **public** on the owner's channel [Loop Physics](https://www.youtube.com/@LoopPhysics-420/shorts).
`videos.list` returned `privacyStatus: public` right after the upload. The public oEmbed endpoint and the channel page
still showed it as public afterwards.

## Visibility (videos set to Private after videos.insert)

We are **not** experiencing this issue. Before the review we had paused automated uploads as a precaution
(`"upload_enabled": false` in the channel config). We did this because YouTube documents that uploads from unaudited
API projects can be restricted to private. While uploads were paused, the owner uploaded by hand and the tool only set
the metadata with `videos.update`.

The test upload above was requested as `public` and stayed public. With the review completed, the tool would publish
up to three Loop Physics videos a day this way.
