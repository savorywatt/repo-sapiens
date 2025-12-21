// Obstacle (pipe) system
class Obstacle {
    constructor(x, gapY, gapSize) {
        this.x = x;
        this.width = 60;
        this.gapY = gapY;
        this.gapSize = gapSize;
        this.scored = false;
        this.speed = 2;
    }

    update() {
        this.x -= this.speed;
    }

    draw(ctx, canvasHeight) {
        const pipeColor = '#2ECC71';
        const pipeHighlight = '#3498DB';

        // Top pipe
        const topHeight = this.gapY - this.gapSize / 2;
        this.drawPipe(ctx, this.x, 0, this.width, topHeight, pipeColor, pipeHighlight);

        // Bottom pipe
        const bottomY = this.gapY + this.gapSize / 2;
        const bottomHeight = canvasHeight - bottomY;
        this.drawPipe(ctx, this.x, bottomY, this.width, bottomHeight, pipeColor, pipeHighlight);
    }

    drawPipe(ctx, x, y, width, height, color, highlight) {
        // Main pipe body
        ctx.fillStyle = color;
        ctx.fillRect(x, y, width, height);

        // Pipe cap
        const capHeight = 25;
        const capWidth = width + 10;
        const capX = x - 5;

        if (y === 0) {
            // Top pipe cap at bottom
            ctx.fillStyle = highlight;
            ctx.fillRect(capX, height - capHeight, capWidth, capHeight);
        } else {
            // Bottom pipe cap at top
            ctx.fillStyle = highlight;
            ctx.fillRect(capX, y, capWidth, capHeight);
        }

        // Pipe highlights
        ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.fillRect(x + 5, y, 10, height);
    }

    collidesWith(bird) {
        const birdBounds = bird.getBounds();

        // Check if bird is horizontally aligned with pipe
        if (birdBounds.x + birdBounds.width < this.x ||
            birdBounds.x > this.x + this.width) {
            return false;
        }

        // Check if bird hits top or bottom pipe
        const topPipeBottom = this.gapY - this.gapSize / 2;
        const bottomPipeTop = this.gapY + this.gapSize / 2;

        if (birdBounds.y < topPipeBottom ||
            birdBounds.y + birdBounds.height > bottomPipeTop) {
            return true;
        }

        return false;
    }

    isOffScreen() {
        return this.x + this.width < 0;
    }

    isPassed(bird) {
        return !this.scored && bird.x > this.x + this.width;
    }
}

class ObstacleManager {
    constructor(canvasWidth, canvasHeight) {
        this.obstacles = [];
        this.canvasWidth = canvasWidth;
        this.canvasHeight = canvasHeight;
        this.spawnTimer = 0;
        this.spawnInterval = 120; // frames between obstacles
        this.gapSize = 150; // Vertical gap size
    }

    reset() {
        this.obstacles = [];
        this.spawnTimer = 60; // Start spawning after 1 second
    }

    update() {
        // Update existing obstacles
        this.obstacles.forEach(obstacle => obstacle.update());

        // Remove off-screen obstacles
        this.obstacles = this.obstacles.filter(obs => !obs.isOffScreen());

        // Spawn new obstacles
        this.spawnTimer++;
        if (this.spawnTimer >= this.spawnInterval) {
            this.spawn();
            this.spawnTimer = 0;
        }
    }

    spawn() {
        // Random gap position (ensure it's not too high or too low)
        const minY = 100;
        const maxY = this.canvasHeight - 100;
        const gapY = Math.random() * (maxY - minY) + minY;

        const obstacle = new Obstacle(this.canvasWidth, gapY, this.gapSize);
        this.obstacles.push(obstacle);
    }

    draw(ctx) {
        this.obstacles.forEach(obstacle => obstacle.draw(ctx, this.canvasHeight));
    }

    checkCollisions(bird) {
        return this.obstacles.some(obstacle => obstacle.collidesWith(bird));
    }

    checkScoring(bird) {
        let scored = 0;
        this.obstacles.forEach(obstacle => {
            if (obstacle.isPassed(bird)) {
                obstacle.scored = true;
                scored++;
            }
        });
        return scored;
    }
}
