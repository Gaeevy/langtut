// Mobile-specific JavaScript functionality

class MobileEnhancements {
    constructor() {
        this.init();
    }

    init() {
        this.setupPWA();
        this.setupSwipeGestures();
        this.setupTouchFeedback();
        this.setupKeyboardHandling();
        this.setupOfflineSupport();
    }

    // PWA Installation
    setupPWA() {
        let deferredPrompt;

        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            this.showInstallButton();
        });

        // Handle install button click
        const installBtn = document.getElementById('install-btn');
        if (installBtn) {
            installBtn.addEventListener('click', async () => {
                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    const { outcome } = await deferredPrompt.userChoice;
                    console.log(`User response to install prompt: ${outcome}`);
                    deferredPrompt = null;
                    this.hideInstallButton();
                }
            });
        }
    }

    showInstallButton() {
        const installBanner = document.createElement('div');
        installBanner.id = 'install-banner';
        installBanner.className = 'alert alert-info d-flex justify-content-between align-items-center';
        installBanner.innerHTML = `
            <span><i class="bi bi-download"></i> Install app for better experience</span>
            <button id="install-btn" class="btn btn-sm btn-primary">Install</button>
        `;

        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(installBanner, container.firstChild);
        }
    }

    hideInstallButton() {
        const banner = document.getElementById('install-banner');
        if (banner) {
            banner.remove();
        }
    }

    // Swipe gestures for flashcards
    setupSwipeGestures() {
        const card = document.querySelector('.language-card');
        if (!card) return;

        let startX, startY, currentX, currentY;
        let isSwipeActive = false;

        card.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            isSwipeActive = true;
        }, { passive: true });

        card.addEventListener('touchmove', (e) => {
            if (!isSwipeActive) return;

            currentX = e.touches[0].clientX;
            currentY = e.touches[0].clientY;

            const deltaX = currentX - startX;
            const deltaY = currentY - startY;

            // Only handle horizontal swipes
            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                e.preventDefault();
                card.style.transform = `translateX(${deltaX}px) rotate(${deltaX * 0.1}deg)`;

                // Visual feedback
                if (deltaX > 50) {
                    card.style.backgroundColor = '#d4edda'; // Green tint
                } else if (deltaX < -50) {
                    card.style.backgroundColor = '#f8d7da'; // Red tint
                } else {
                    card.style.backgroundColor = '';
                }
            }
        }, { passive: false });

        card.addEventListener('touchend', (e) => {
            if (!isSwipeActive) return;
            isSwipeActive = false;

            const deltaX = currentX - startX;

            // Reset card position
            card.style.transform = '';
            card.style.backgroundColor = '';

            // Trigger actions based on swipe distance
            if (Math.abs(deltaX) > 100) {
                if (deltaX > 0) {
                    this.handleSwipeRight();
                } else {
                    this.handleSwipeLeft();
                }
            }
        }, { passive: true });
    }

    handleSwipeRight() {
        // Could be used for "easy" or "correct" actions
        console.log('Swiped right');
        // You could auto-submit with a positive answer or show hint
    }

    handleSwipeLeft() {
        // Could be used for "hard" or "incorrect" actions
        console.log('Swiped left');
        // You could auto-submit with a negative answer or skip
    }

    // Touch feedback for buttons
    setupTouchFeedback() {
        const buttons = document.querySelectorAll('.btn');

        buttons.forEach(button => {
            button.addEventListener('touchstart', () => {
                button.style.transform = 'scale(0.95)';
            }, { passive: true });

            button.addEventListener('touchend', () => {
                setTimeout(() => {
                    button.style.transform = '';
                }, 100);
            }, { passive: true });
        });
    }

    // Mobile keyboard handling
    setupKeyboardHandling() {
        const answerInput = document.getElementById('answer');
        if (!answerInput) return;

        // Handle virtual keyboard
        let initialViewportHeight = window.innerHeight;

        window.addEventListener('resize', () => {
            const currentHeight = window.innerHeight;
            const heightDifference = initialViewportHeight - currentHeight;

            // If keyboard is likely open (height reduced significantly)
            if (heightDifference > 150) {
                document.body.classList.add('keyboard-open');
                // Scroll input into view
                setTimeout(() => {
                    answerInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 100);
            } else {
                document.body.classList.remove('keyboard-open');
            }
        });

        // Auto-capitalize first letter
        answerInput.addEventListener('input', (e) => {
            if (e.target.value.length === 1) {
                e.target.value = e.target.value.charAt(0).toUpperCase() + e.target.value.slice(1);
            }
        });
    }

    // Basic offline support
    setupOfflineSupport() {
        window.addEventListener('online', () => {
            this.showConnectionStatus('Connected', 'success');
        });

        window.addEventListener('offline', () => {
            this.showConnectionStatus('Offline', 'warning');
        });
    }

    showConnectionStatus(message, type) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed top-0 start-50 translate-middle-x mt-3`;
        toast.style.zIndex = '9999';
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new MobileEnhancements();
});

// Service Worker registration
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then((registration) => {
                console.log('SW registered: ', registration);
            })
            .catch((registrationError) => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}
