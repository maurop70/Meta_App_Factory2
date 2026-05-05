document.addEventListener('DOMContentLoaded', () => {
    const gridContainer = document.querySelector('.grid-container');
    let cards = Array.from(document.querySelectorAll('.app-card'));
    
    // Load saved order from localStorage
    const savedOrder = JSON.parse(localStorage.getItem('appHubOrder'));
    if (savedOrder && savedOrder.length > 0) {
        // Reorder DOM elements based on saved IDs
        savedOrder.forEach(id => {
            const card = document.getElementById(id);
            if (card) {
                gridContainer.appendChild(card);
            }
        });
        // Re-query cards after reordering to maintain correct index for animation
        cards = Array.from(document.querySelectorAll('.app-card'));
    }

    // Add subtle entrance animation to cards
    cards.forEach((card, index) => {
        // Make card draggable
        card.setAttribute('draggable', 'true');

        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            card.style.transition = 'opacity 0.6s ease, transform 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
            
            // Reset transition for hover effects after entrance animation
            setTimeout(() => {
                card.style.transition = 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
            }, 600);
        }, 100 * index); // Staggered animation
    });

    // Drag and Drop Logic
    let draggedCard = null;

    cards.forEach(card => {
        card.addEventListener('dragstart', (e) => {
            draggedCard = card;
            e.dataTransfer.effectAllowed = 'move';
            // Slight delay so the UI shows the drag ghost properly before hiding the original
            setTimeout(() => card.classList.add('dragging'), 0);
        });

        card.addEventListener('dragend', () => {
            draggedCard = null;
            card.classList.remove('dragging');
            
            // Save the new order to localStorage
            const newOrder = Array.from(gridContainer.querySelectorAll('.app-card')).map(c => c.id);
            localStorage.setItem('appHubOrder', JSON.stringify(newOrder));
        });

        card.addEventListener('dragover', (e) => {
            e.preventDefault(); // Necessary to allow dropping
            e.dataTransfer.dropEffect = 'move';
            if (draggedCard === card || !draggedCard) return;

            // Determine relative mouse position to place before or after
            const rect = card.getBoundingClientRect();
            // We use the center of the target card to decide whether to place before or after
            // This works well for a grid layout
            const targetXCenter = rect.left + rect.width / 2;
            const mouseX = e.clientX;
            
            if (mouseX < targetXCenter) {
                gridContainer.insertBefore(draggedCard, card);
            } else {
                gridContainer.insertBefore(draggedCard, card.nextSibling);
            }
        });

        // Handle clicks for standby apps
        card.addEventListener('click', (e) => {
            const href = card.getAttribute('href');
            if (href === '#') {
                e.preventDefault();
                
                // Add a small shake animation for inactive apps
                card.style.transform = 'translateX(5px)';
                setTimeout(() => card.style.transform = 'translateX(-5px)', 50);
                setTimeout(() => card.style.transform = 'translateX(5px)', 100);
                setTimeout(() => card.style.transform = 'translateX(0)', 150);
                
                console.log('App currently in standby mode.');
            }
        });
    });
});
