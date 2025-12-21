// Main game logic and loop
class FlappyBirdGame {
    constructor() {
        this.canvas = document.getElementById('game-canvas');
        this.ctx = this.canvas.getContext('2d');

        this.setupCanvas();
        this.gameState = 'MENU'; // MENU, PLAYING, GAME_OVER
        this.bird = null;
        this.obstacleManager = null;
        this.score = 0;
        this.selectedBirdType = null;

        this.setupEventListeners();
        window.uiManager.showScreen('selection');
    }

    setupCanvas() {
        this.canvas.width = 400;
        this.canvas.height = 600;
    }

    setupEventListeners() {
        // Bird selection
        document.querySelectorAll('.bird-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const birdType = e.currentTarget.dataset.bird;
                this.selectBird(birdType);
            });
        });

        // Game controls
        this.canvas.addEventListener('click', () => this.handleInput());
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space') {
                e.preventDefault();
                this.handleInput();
            }
        });

        // Touch support for mobile
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.handleInput();
        });

        // Restart button
        document.getElementById('restart-button').addEventListener('click', () => {
            this.startGame(this.selectedBirdType);
        });

        // Change bird button
        document.getElementById('change-bird-button').addEventListener('click', () => {
            window.uiManager.showScreen('selection');
            this.gameState = 'MENU';
        });

        // Mute button
        document.getElementById('mute-button').addEventListener('click', () => {
            const isMuted = window.gameAudio.toggle();
            window.uiManager.updateMuteButton(isMuted);
        });
    }

    selectBird(birdType) {
        this.selectedBirdType = birdType;
        this.startGame(birdType);
    }

    startGame(birdType) {
        this.bird = new Bird(birdType, 100, this.canvas.height / 2);
        this.obstacleManager = new ObstacleManager(this.canvas.width, this.canvas.height);
        this.obstacleManager.reset();
        this.score = 0;
        this.gameState = 'PLAYING';

        window.uiManager.showScreen('game');
        window.uiManager.updateScore(0);

        if (!this.animationFrameId) {
            this.gameLoop();
        }
    }

    handleInput() {
        if (this.gameState === 'PLAYING') {
            this.bird.flap();
        }
    }

    update() {
        if (this.gameState !== 'PLAYING') return;

        // Update bird
        this.bird.update();

        // Update obstacles
        this.obstacleManager.update();

        // Check for scoring
        const pointsScored = this.obstacleManager.checkScoring(this.bird);
        if (pointsScored > 0) {
            this.score += pointsScored;
            window.uiManager.updateScore(this.score);
            window.gameAudio.playScore();
        }

        // Check collisions
        const hitObstacle = this.obstacleManager.checkCollisions(this.bird);
        const hitGround = this.bird.y + this.bird.radius >= this.canvas.height;
        const hitCeiling = this.bird.y - this.bird.radius <= 0;

        if (hitObstacle || hitGround || hitCeiling) {
            this.gameOver();
        }
    }

    draw() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw background gradient
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#87CEEB');
        gradient.addColorStop(1, '#E0F6FF');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw clouds
        this.drawClouds();

        // Draw game objects
        if (this.bird) {
            this.bird.draw(this.ctx);
        }

        if (this.obstacleManager) {
            this.obstacleManager.draw(this.ctx);
        }

        // Draw ground
        this.drawGround();
    }

    drawClouds() {
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';

        // Simple static clouds
        const clouds = [
            { x: 50, y: 80, size: 30 },
            { x: 200, y: 120, size: 25 },
            { x: 320, y: 90, size: 28 },
            { x: 150, y: 200, size: 22 }
        ];

        clouds.forEach(cloud => {
            this.ctx.beginPath();
            this.ctx.arc(cloud.x, cloud.y, cloud.size, 0, Math.PI * 2);
            this.ctx.arc(cloud.x + cloud.size * 0.7, cloud.y, cloud.size * 0.8, 0, Math.PI * 2);
            this.ctx.arc(cloud.x - cloud.size * 0.7, cloud.y, cloud.size * 0.7, 0, Math.PI * 2);
            this.ctx.fill();
        });
    }

    drawGround() {
        const groundHeight = 50;
        const gradient = this.ctx.createLinearGradient(
            0, this.canvas.height - groundHeight,
            0, this.canvas.height
        );
        gradient.addColorStop(0, '#8B4513');
        gradient.addColorStop(1, '#654321');

        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, this.canvas.height - groundHeight, this.canvas.width, groundHeight);

        // Grass on top
        this.ctx.fillStyle = '#228B22';
        this.ctx.fillRect(0, this.canvas.height - groundHeight, this.canvas.width, 10);
    }

    gameOver() {
        this.gameState = 'GAME_OVER';
        window.gameAudio.playGameOver();
        window.uiManager.showGameOver(this.score);
    }

    gameLoop() {
        this.update();
        this.draw();
        this.animationFrameId = requestAnimationFrame(() => this.gameLoop());
    }
}

// Initialize game when page loads
window.addEventListener('load', () => {
    new FlappyBirdGame();
});
