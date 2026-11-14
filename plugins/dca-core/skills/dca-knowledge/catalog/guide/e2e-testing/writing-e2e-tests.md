---
type: Section
title: Writing E2E Tests
chapter: E2E Testing for Domain-Centric Architecture
source: guide
tags: [guide, section]
---

### A happy-path test

A story's end-to-end test proves its happy path, and nothing before it: the preconditions come in through the
input ports ([Preconditions through the input ports](#preconditions-through-the-input-ports)), the test performs
the one interaction the story is about and asserts what the user sees.

```java
@DisplayName("Guest checkout")
class PlaceOrderAsGuestE2ETest extends BaseE2ETest {

    @Test
    @DisplayName("A guest places an order for the items in the cart")
    void placesAnOrderAsGuest() {
        CartId cart = cartWith(unique("Desk lamp"));          // precondition, through the input port

        ReviewPage review = ReviewPage.navigateTo(page, cart);
        ConfirmationPage confirmation = review.placeOrder();  // the one interaction under test

        assertTrue(confirmation.isOrderConfirmed());
    }
}
```

`cartWith` calls the use cases the pages call — add an item, enter buyer, delivery and payment — so the review page
opens on a state the application itself produced. Each of those steps has an end-to-end test of its own, the
happy path of the story that delivered it.

### A journey test

Only a journey test walks the whole way, page by page, to the outcome of an epic
([Test Levels](/guide/testing-levels/smoke-test-happy-path-test-journey-test.md)). It is a regression guard over
delivered stories, not a story's criterion, and it is green when it is written.

```java
@DisplayName("Guest Checkout E2E Tests")
class CheckoutGuestE2ETest extends BaseE2ETest {

    @Test
    @DisplayName("Complete checkout flow as guest user")
    void completeGuestCheckoutFlow() {
        // the journey: every step through the page, from the catalog to the confirmation

        // Step 1: Browse catalog and add product
        ProductCatalogPage catalog = ProductCatalogPage.navigateTo(page);
        ProductDetailPage detail = catalog.viewFirstProduct();
        detail.addToCart();

        // Step 2: Verify cart and start checkout
        CartPage cart = CartPage.navigateTo(page);
        assertTrue(cart.hasItems(), "Cart should have at least one item");

        // Step 3: Fill buyer information
        BuyerInfoPage buyer = cart.proceedToCheckout();
        DeliveryPage delivery = buyer
            .fillBuyerInfo("guest@example.com", "Test", "Guest", "+1-555-0100")
            .continueToDelivery();

        // Step 4: Fill delivery information
        PaymentPage payment = delivery
            .fillAddress("123 Main Street", "Springfield", "12345", "US", "IL")
            .selectFirstShippingOption()
            .continueToPayment();

        // Step 5: Select payment
        ReviewPage review = payment
            .selectFirstPaymentProvider()
            .continueToReview();

        // Step 6: Verify and place order
        assertTrue(review.showsEmail("guest@example.com"));
        ConfirmationPage confirmation = review.placeOrder();

        // Step 7: Verify confirmation
        assertTrue(confirmation.isOrderConfirmed());
    }
}
```

### Test Characteristics

- **Readable** - Tests read like user stories
- **Isolated** - Each test starts with fresh browser context
- **Focused** - One flow per test
- **Verifiable** - Clear assertions at key points

---
