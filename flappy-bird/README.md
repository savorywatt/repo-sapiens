# Flappy Birds - Multi-Bird Clone

A fun, web-based Flappy Bird clone featuring three different playable birds, each with unique flight characteristics!

## Features

- 🐦 **Three Playable Birds**:
  - **Robin**: Balanced bird with medium speed and jump strength
  - **Swallow**: Fast bird with quick jumps and high horizontal speed
  - **Seagull**: Heavy bird with strong jumps but slower movement

- 🎮 **Classic Gameplay**: Simple tap/click controls with smooth physics
- 🏆 **Score Tracking**: High score persists in browser localStorage
- 🔊 **Sound Effects**: Web Audio API-powered sound effects
- 📱 **Responsive Design**: Works on desktop and mobile devices
- 🎨 **Beautiful UI**: Gradient backgrounds, smooth animations

## How to Play

1. **Select Your Bird**: Choose between Robin, Swallow, or Seagull
2. **Control**:
   - Press SPACE on keyboard
   - Click/Tap on the canvas
3. **Objective**: Navigate through pipes without hitting them or the ground
4. **Scoring**: Earn 1 point for each pipe you successfully pass

## Installation

No installation required! Just open `index.html` in a modern web browser.

### Running Locally

```bash
# Option 1: Open directly
open index.html

# Option 2: Use a local server (recommended)
python -m http.server 8000
# Then visit http://localhost:8000

# Option 3: Use Node.js http-server
npx http-server .
```

## File Structure

```
flappy-bird/
├── index.html          # Main HTML file
├── styles.css          # All styles and animations
├── game.js             # Main game loop and logic
├── bird.js             # Bird class with physics
├── obstacles.js        # Pipe generation and collision
├── ui.js               # UI management and high scores
├── audio.js            # Sound effects system
└── README.md           # This file
```

## Technologies Used

- **Vanilla JavaScript (ES6+)**: No external dependencies
- **HTML5 Canvas**: For smooth 2D rendering
- **Web Audio API**: For procedural sound generation
- **CSS3**: For beautiful UI and animations
- **LocalStorage**: For high score persistence

## Browser Compatibility

Works on all modern browsers:
- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

## Bird Characteristics

| Bird    | Gravity | Jump Strength | Speed | Best For          |
|---------|---------|---------------|-------|-------------------|
| Robin   | 0.25    | -4.5          | 2.5   | Beginners         |
| Swallow | 0.20    | -4.0          | 3.5   | Experienced       |
| Seagull | 0.30    | -5.0          | 2.0   | Advanced players  |

## Controls

- **Desktop**: SPACE key or Mouse Click
- **Mobile**: Tap anywhere on the screen
- **Mute**: Click the speaker icon to toggle sound

## Development

This game was built following modern JavaScript best practices:
- Object-oriented design with ES6 classes
- Separation of concerns (MVC pattern)
- Smooth 60fps animation using requestAnimationFrame
- Responsive canvas rendering
- Collision detection using bounding boxes

### Key Code Features

- **Physics System**: Realistic gravity and momentum
- **Procedural Generation**: Random pipe placement
- **Sound Synthesis**: No audio files - all sounds generated via Web Audio API
- **State Management**: Clean separation between menu, playing, and game over states

## Credits

Built as a demonstration of the builder automation system for planning and implementing web games.

Original Flappy Bird concept by Dong Nguyen.

## License

This is a learning/demonstration project. Feel free to use and modify!

## Future Enhancements

Potential improvements:
- Add difficulty levels (pipe speed, gap size)
- Implement power-ups
- Add different backgrounds/themes
- Multiplayer mode
- Leaderboards with backend
- More bird types with special abilities

## Playing Tips

1. **Robin** is perfect for learning the game mechanics
2. **Swallow** requires quick reflexes but covers distance fast
3. **Seagull** is challenging but the strong jump can save you

Happy flapping! 🐦
