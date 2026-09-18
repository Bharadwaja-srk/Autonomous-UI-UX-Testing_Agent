/**
 * ApexGear Demo E-Commerce Store Frontend Logic
 */

const PRODUCTS = [
    {
        id: "prod-1",
        title: "Apex Velocity Blue Running Shoe",
        category: "running",
        color: "blue",
        price: 139.99,
        emoji: "👟",
        rating: 4.9,
        desc: "Engineered with nitrogen-infused foam and breathable knit for ultra-responsive marathon performance.",
        badge: "BESTSELLER"
    },
    {
        id: "prod-2",
        title: "Apex Trail Pro Blue 2.0",
        category: "trail",
        color: "blue",
        price: 149.99,
        emoji: "🥾",
        rating: 4.8,
        desc: "Aggressive lug traction and waterproof ripstop upper for rugged mountain trails and off-road running.",
        badge: "ALL-WEATHER"
    },
    {
        id: "prod-3",
        title: "Apex Swift Sprint Blue",
        category: "running",
        color: "blue",
        price: 119.99,
        emoji: "👟",
        rating: 4.7,
        desc: "Ultra-lightweight sprint shoe designed for 5K races and tempo training sessions.",
        badge: "LIGHTWEIGHT"
    },
    {
        id: "prod-4",
        title: "Apex Stealth Trainer Black",
        category: "training",
        color: "black",
        price: 109.99,
        emoji: "👟",
        rating: 4.6,
        desc: "Versatile gym and cross-training athletic shoe with stable flat heel support.",
        badge: "VERSATILE"
    }
];

class StoreApp {
    constructor() {
        this.cart = [];
        this.selectedProduct = PRODUCTS[0];
        this.selectedSize = "9.0";
        this.hasShownPromo = false;
        this.init();
    }

    init() {
        this.renderFeatured();
        this.updateCartUI();
    }

    showView(viewId) {
        document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
        const target = document.getElementById(`${viewId}View`);
        if (target) {
            target.classList.add('active');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    renderFeatured() {
        const container = document.getElementById('featuredGrid');
        if (!container) return;
        container.innerHTML = PRODUCTS.map(p => this.createProductCard(p)).join('');
    }

    createProductCard(product) {
        return `
        <div class="product-card" id="card-${product.id}">
            <div class="product-card-img" onclick="app.viewProduct('${product.id}')">
                <span class="product-card-badge">${product.badge}</span>
                <span>${product.emoji}</span>
            </div>
            <div class="product-card-body">
                <div class="product-card-category">${product.category} &bull; ${product.color}</div>
                <div class="product-card-title" onclick="app.viewProduct('${product.id}')">${product.title}</div>
                <div class="product-card-price">$${product.price.toFixed(2)}</div>
                <div class="product-card-actions">
                    <button class="btn-secondary" onclick="app.viewProduct('${product.id}')">Details</button>
                    <button class="btn-primary" onclick="app.addToCartDirect('${product.id}')">Add to Cart</button>
                </div>
            </div>
        </div>
        `;
    }

    handleSearch() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) return;
        this.searchQuery(query);
    }

    searchQuery(query) {
        const q = query.toLowerCase();
        document.getElementById('searchKeyword').innerText = `"${query}"`;
        
        const filtered = PRODUCTS.filter(p => 
            p.title.toLowerCase().includes(q) || 
            p.category.toLowerCase().includes(q) || 
            p.color.toLowerCase().includes(q) ||
            p.desc.toLowerCase().includes(q) ||
            (q.includes("running") && p.category === "running") ||
            (q.includes("blue") && p.color === "blue") ||
            (q.includes("shoe") || q.includes("shoes"))
        );

        const grid = document.getElementById('searchResultsGrid');
        const countEl = document.getElementById('resultsCount');
        
        countEl.innerText = `${filtered.length} item${filtered.length === 1 ? '' : 's'} found`;
        grid.innerHTML = filtered.length > 0 
            ? filtered.map(p => this.createProductCard(p)).join('')
            : `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #94a3b8;">No matching products found.</div>`;

        this.showView('search');

        // Intentional UX popup friction trigger on first search
        if (!this.hasShownPromo) {
            setTimeout(() => {
                this.openPromo();
                this.hasShownPromo = true;
            }, 600);
        }
    }

    showCategory(category) {
        this.searchQuery(category);
    }

    filterCategory(cat) {
        document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
        if (event && event.target) event.target.classList.add('active');

        if (cat === 'all') {
            this.searchQuery('shoes');
        } else {
            this.searchQuery(cat);
        }
    }

    viewProduct(productId) {
        const prod = PRODUCTS.find(p => p.id === productId);
        if (!prod) return;
        this.selectedProduct = prod;

        document.getElementById('detailTitle').innerText = prod.title;
        document.getElementById('detailCategory').innerText = `${prod.category.toUpperCase()} &bull; ${prod.color.toUpperCase()}`;
        document.getElementById('detailPrice').innerText = `$${prod.price.toFixed(2)}`;
        document.getElementById('detailDesc').innerText = prod.desc;
        document.getElementById('detailImage').innerHTML = `<span>${prod.emoji}</span>`;

        this.showView('productDetail');
    }

    selectSize(btn) {
        document.querySelectorAll('.size-chip').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        this.selectedSize = btn.innerText;
    }

    addToCartFromDetail() {
        if (!this.selectedProduct) return;
        this.addToCartDirect(this.selectedProduct.id);
    }

    addToCartDirect(productId) {
        const prod = PRODUCTS.find(p => p.id === productId);
        if (!prod) return;

        const existing = this.cart.find(item => item.product.id === productId && item.size === this.selectedSize);
        if (existing) {
            existing.quantity += 1;
        } else {
            this.cart.push({
                product: prod,
                size: this.selectedSize,
                quantity: 1
            });
        }

        this.updateCartUI();
        this.showToast(`✅ "${prod.title}" added to cart!`);
        this.toggleCart(true);
    }

    updateCartUI() {
        const totalCount = this.cart.reduce((sum, item) => sum + item.quantity, 0);
        const subtotal = this.cart.reduce((sum, item) => sum + (item.product.price * item.quantity), 0);

        document.getElementById('cartCount').innerText = totalCount;
        document.getElementById('drawerCartCount').innerText = totalCount;
        document.getElementById('cartSubtotal').innerText = `$${subtotal.toFixed(2)}`;

        const container = document.getElementById('cartItemsContainer');
        if (!container) return;

        if (this.cart.length === 0) {
            container.innerHTML = `<div style="text-align: center; color: #64748b; padding: 40px 0;">Your shopping cart is empty.</div>`;
            return;
        }

        container.innerHTML = this.cart.map((item, idx) => `
            <div class="cart-item-card">
                <div class="cart-item-img">${item.product.emoji}</div>
                <div class="cart-item-info">
                    <div class="cart-item-title">${item.product.title}</div>
                    <div class="cart-item-sub">Size: ${item.size} &bull; Qty: ${item.quantity}</div>
                    <div class="cart-item-price">$${(item.product.price * item.quantity).toFixed(2)}</div>
                </div>
                <button style="background:transparent;border:none;color:#ef4444;cursor:pointer;font-size:1.1rem;" onclick="app.removeFromCart(${idx})">🗑️</button>
            </div>
        `).join('');
    }

    removeFromCart(index) {
        this.cart.splice(index, 1);
        this.updateCartUI();
    }

    toggleCart(forceOpen) {
        const drawer = document.getElementById('cartDrawer');
        const overlay = document.getElementById('cartOverlay');
        const shouldOpen = forceOpen !== undefined ? forceOpen : !drawer.classList.contains('active');

        if (shouldOpen) {
            drawer.classList.add('active');
            overlay.classList.add('active');
        } else {
            drawer.classList.remove('active');
            overlay.classList.remove('active');
        }
    }

    proceedToCheckout() {
        this.toggleCart(false);
        const list = document.getElementById('checkoutSummaryList');
        const totalEl = document.getElementById('checkoutTotalAmount');
        const subtotal = this.cart.reduce((sum, item) => sum + (item.product.price * item.quantity), 0);

        list.innerHTML = this.cart.map(i => `
            <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.9rem;">
                <span>${i.product.title} (x${i.quantity})</span>
                <span style="font-weight:700;">$${(i.product.price * i.quantity).toFixed(2)}</span>
            </div>
        `).join('');

        totalEl.innerText = `$${subtotal.toFixed(2)}`;
        this.showView('checkout');
    }

    completeOrder() {
        this.cart = [];
        this.updateCartUI();
        this.showView('success');
    }

    openPromo() {
        document.getElementById('promoModal').classList.add('active');
    }

    closePromo() {
        document.getElementById('promoModal').classList.remove('active');
    }

    showToast(message) {
        const t = document.getElementById('toast');
        t.innerText = message;
        t.classList.add('active');
        setTimeout(() => {
            t.classList.remove('active');
        }, 3000);
    }
}

const app = new StoreApp();
window.app = app;
