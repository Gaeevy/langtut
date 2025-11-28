/**
 * Index page JavaScript
 * Handles listening mode initialization
 */

/**
 * Initialize listening functionality
 */
function initListeningMode() {
    const listenButtons = document.querySelectorAll('.listen-btn');

    listenButtons.forEach(button => {
        button.addEventListener('click', async function() {
            const tabName = this.getAttribute('data-tab-name');

            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('listeningModal'));
            modal.show();

            // Update modal title
            const modalLabel = document.getElementById('listeningModalLabel');
            if (modalLabel) {
                modalLabel.textContent = `Listen: ${tabName}`;
            }

            // Start listening session
            if (window.listeningManager) {
                await window.listeningManager.startListening(tabName);
            }
        });
    });
}

/**
 * Initialize index page
 */
function initIndexPage() {
    initListeningMode();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initIndexPage);
