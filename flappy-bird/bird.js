// Bird class with physics and rendering
class Bird {
    constructor(type, x, y) {
        this.type = type;
        this.x = x;
        this.y = y;
        this.velocity = 0;
        this.rotation = 0;
        this.radius = 15;

        // Bird-specific characteristics
        const characteristics = {
            robin: {
                gravity: 0.25,
                jumpStrength: -4.5,
                horizontalSpeed: 2.5,
                color: '#FF6B6B',
                name: 'Robin'
            },
            swallow: {
                gravity: 0.20,
                jumpStrength: -4.0,
                horizontalSpeed: 3.5,
                color: '#4ECDC4',
                name: 'Swallow'
            },
            seagull: {
                gravity: 0.30,
                jumpStrength: -5.0,
                horizontalSpeed: 2.0,
                color: '#95E1D3',
                name: 'Seagull'
            }
        };

        const char = characteristics[type];
        this.gravity = char.gravity;
        this.jumpStrength = char.jumpStrength;
        this.horizontalSpeed = char.horizontalSpeed;
        this.color = char.color;
        this.name = char.name;
    }

    flap() {
        this.velocity = this.jumpStrength;
        if (window.gameAudio) {
            window.gameAudio.playJump();
        }
    }

    update() {
        // Apply gravity
        this.velocity += this.gravity;
        this.y += this.velocity;

        // Update rotation based on velocity
        this.rotation = Math.min(Math.max(this.velocity * 3, -30), 90);
    }

    draw(ctx) {
        ctx.save();

        // Translate to bird position
        ctx.translate(this.x, this.y);
        ctx.rotate(this.rotation * Math.PI / 180);

        // Draw bird body (circle with gradient)
        const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, this.radius);
        gradient.addColorStop(0, this.lightenColor(this.color, 20));
        gradient.addColorStop(1, this.color);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(0, 0, this.radius, 0, Math.PI * 2);
        ctx.fill();

        // Draw wing
        ctx.fillStyle = 'white';
        ctx.beginPath();
        ctx.ellipse(5, 0, 8, 12, 0, 0, Math.PI * 2);
        ctx.fill();

        // Draw eye
        ctx.fillStyle = 'white';
        ctx.beginPath();
        ctx.arc(-5, -5, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = 'black';
        ctx.beginPath();
        ctx.arc(-4, -5, 2, 0, Math.PI * 2);
        ctx.fill();

        // Draw beak
        ctx.fillStyle = '#FFD700';
        ctx.beginPath();
        ctx.moveTo(-12, 0);
        ctx.lineTo(-18, -3);
        ctx.lineTo(-18, 3);
        ctx.closePath();
        ctx.fill();

        ctx.restore();
    }

    lightenColor(color, percent) {
        const num = parseInt(color.replace("#",""), 16);
        const amt = Math.round(2.55 * percent);
        const R = (num >> 16) + amt;
        const G = (num >> 8 & 0x00FF) + amt;
        const B = (num & 0x0000FF) + amt;
        return "#" + (0x1000000 + (R<255?R<1?0:R:255)*0x10000 +
            (G<255?G<1?0:G:255)*0x100 +
            (B<255?B<1?0:B:255))
            .toString(16).slice(1);
    }

    getBounds() {
        return {
            x: this.x - this.radius,
            y: this.y - this.radius,
            width: this.radius * 2,
            height: this.radius * 2
        };
    }
}
