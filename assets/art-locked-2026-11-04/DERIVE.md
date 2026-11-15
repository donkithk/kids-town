# How the A and C cutouts were made

Originals in `originals/` are the locked JPEGs. SHA-256:

| File | SHA-256 |
| --- | --- |
| `ui-town-wood-frame.jpg` | `a5c8cee063d25580469f4309465ce3c02bbceced9bfcfb306826f315611b1fa2` |
| `bg-town-plaza.jpg` | `57835c6a555e260d6ed688968866087c420ecbf83767413bf8a2e0f5fd29a388` |
| `building-adventure-guild.jpg` | `f42e42122f8539b85db1f605939e96375d7e59619053f97af79c6b5dafc410e0` |

`scripts/derive_art_abc.py` rewrites only `derived/`. It does not edit the JPEGs.

## A — wood frame

`derived/ui-town-wood-frame-cutout.png` is 1280×720 RGBA.

The interior cream is one connected region. A flood from the center keeps a pixel only while its RGB distance to the center pixel `(252, 244, 225)` is at most 22. That removes the cream opening and leaves the wood, including the dark inner bevel (those pixels are far from cream). The outer rounded corners are a cooler cream disconnected from the center. Each corner is flooded from its own color, and only if that corner pixel is itself cream (`R>220`, `G>210`, `B>190`, distance to the interior cream under 48). The bottom-right canvas corner is wood and is not seeded.

There is no 9-slice. The PNG is the full frame with a transparent opening.

## B — plaza, not derived

`bg-town-plaza.jpg` stays the locked JPEG. No meadow PNG is generated.

The picture is a 6×6 diamond, a plank cross, and a slate ring. The live map is an 8×8 plus a locked ring, scrolled inside the town panel, with its own slabs and hitboxes. The painted diamond also sticks out past the map rectangle into the header, footer, and side margins. Putting the JPEG behind the map would show a second grid. Color segmentation could not delete that grid without leaving a readable ghost or eating the trees. So the preview does not paint B.

## C — guild

`derived/building-adventure-guild-cutout.png` is the opaque bounding box of the building (641×833), not the 1024×1024 cream square.

1. Flood from every edge pixel while RGB distance to the corner cream `(251, 239, 215)` is at most 26.
2. Any remaining pixel still within distance 16 of that cream is an enclosed hole (the chimney opening) and is flooded the same way.
3. An opaque pixel that touches transparency, is not grass, banner red, or window blue, and is within distance 58 of cream, gets partial alpha so the halo does not read as a cream rim.
4. Crop to the alpha bounding box. The bottom edge of that crop is the stone plinth. The town sprite pins that edge to the bottom of the origin pad and sets the width to the pad width. The existing CSS contact shadow is not replaced. No anchor number was taken from outside the game.

The stone base, grass tufts, and blue-grey windows stay. They are in the locked JPEG.
