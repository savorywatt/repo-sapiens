// UI Management
class UIManager {
    constructor() {
        this.screens = {
            selection: document.getElementById('bird-selection'),
            game: document.getElementById('game-container'),
            gameOver: document.getElementById('game-over')
        };

        this.elements = {
            currentScore: document.getElementById('current-score'),
            highScore: document.getElementById('high-score'),
            finalScore: document.getElementById('final-score'),
            newHighScore: document.getElementById('new-high-score'),
            muteButton: document.getElementById('mute-button')
        };

        this.highScore = this.loadHighScore();
        this.updateHighScore();
    }

    showScreen(screenName) {
        Object.values(this.screens).forEach(screen => screen.classList.add('hidden'));
        if (this.screens[screenName]) {
            this.screens[screenName].classList.remove('hidden');
        }
    }

    updateScore(score) {
        this.elements.currentScore.textContent = score;
    }

    updateHighScore() {
        this.elements.highScore.textContent = this.highScore;
    }

    showGameOver(score) {
        this.elements.finalScore.textContent = score;

        const isNewHighScore = score > this.highScore;
        if (isNewHighScore) {
            this.highScore = score;
            this.saveHighScore(score);
            this.updateHighScore();
            this.elements.newHighScore.style.display = 'block';
        } else {
            this.elements.newHighScore.style.display = 'none';
        }

        this.showScreen('gameOver');
    }

    loadHighScore() {
        const saved = localStorage.getItem('flappyBirdHighScore');
        return saved ? parseInt(saved) : 0;
    }

    saveHighScore(score) {
        localStorage.setItem('flappyBirdHighScore', score.toString());
    }

    updateMuteButton(isMuted) {
        this.elements.muteButton.textContent = isMuted ? '🔇' : '🔊';
    }
}

// Initialize UI manager
window.uiManager = new UIManager();
