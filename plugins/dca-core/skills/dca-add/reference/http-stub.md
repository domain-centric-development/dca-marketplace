# An HTTP stub for integration tests

What an integration test puts in place of an external system: a real HTTP server on a free port that
answers what the test arranges. The adapter under test talks HTTP to it exactly as it talks to the real
system, so the translation — the request it builds, the status and body it reads, a timeout — is what the
test proves. A mock of the port proves everything except that; a shared or real instance makes the test
pass or fail on another system.

Versions are looked up at setup time (Maven Central for `org.wiremock:wiremock-standalone`, NuGet for
`WireMock.Net`) — the latest stable release, not a beta. The standalone WireMock artifact shades its Jetty,
so it does not clash with the web server of the application.

## Java — WireMock (Gradle, Maven)

The dependency, in the integration source set (or the unit-test one where there is none):

```groovy
testIntegrationImplementation 'org.wiremock:wiremock-standalone:<version>'   // Gradle, integration source set
testImplementation 'org.wiremock:wiremock-standalone:<version>'              // Gradle, no integration source set
```

```xml
<dependency>                                   <!-- Maven -->
  <groupId>org.wiremock</groupId>
  <artifactId>wiremock-standalone</artifactId>
  <version><version></version>
  <scope>test</scope>
</dependency>
```

The smoke test — the stub on a free port, one arranged answer, one call:

```java
class HttpStubSmokeTest {

  @RegisterExtension
  static WireMockExtension provider =
      WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();

  @Test
  void answersWhatTheTestArranged() throws Exception {
    provider.stubFor(get("/status").willReturn(aResponse().withStatus(200).withBody("available")));

    HttpResponse<String> response = HttpClient.newHttpClient()
        .send(HttpRequest.newBuilder(URI.create(provider.baseUrl() + "/status")).build(),
            HttpResponse.BodyHandlers.ofString());

    assertEquals("available", response.body());
  }
}
```

Imports: `com.github.tomakehurst.wiremock.junit5.WireMockExtension`,
`com.github.tomakehurst.wiremock.client.WireMock.*`, `com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig`.

An integration test of an adapter points the application at the stub through configuration — the base
URL is a property, never a constant:

```java
@SpringBootTest
class ProviderAdapterIntegrationTest {

  @RegisterExtension
  static WireMockExtension provider =
      WireMockExtension.newInstance().options(wireMockConfig().dynamicPort()).build();

  @DynamicPropertySource
  static void providerUrl(DynamicPropertyRegistry registry) {
    registry.add("<the adapter's base-url property>", provider::baseUrl);
  }
}
```

A refusal is an arranged status (`aResponse().withStatus(402)`), a timeout an arranged delay longer than the
adapter's (`withFixedDelay(...)`).

Arrange the answer for the request the contract describes, not for any request: match the body's shape,
field types included, so an adapter that sends the wrong type gets no answer instead of a green test.
`equalToJson` with placeholders checks a type that a JSON-path regex cannot see (the regex reads a number as
text):

```json
"bodyPatterns": [{ "equalToJson": { "amount": "${json-unit.regex}^[0-9]+\\.[0-9]{2}$" }, "enablePlaceholders": true }]
```

## .NET — WireMock.Net

The package, in the integration test project (or the unit-test one where there is none):

```bash
dotnet add tests/<Name>.IntegrationTests package WireMock.Net --version <version>
```

The smoke test:

```csharp
public sealed class HttpStubSmokeTest : IDisposable
{
    private readonly WireMockServer _provider = WireMockServer.Start();

    [Fact]
    public async Task AnswersWhatTheTestArranged()
    {
        _provider.Given(Request.Create().WithPath("/status").UsingGet())
            .RespondWith(Response.Create().WithStatusCode(200).WithBody("available"));

        using var client = new HttpClient();
        var body = await client.GetStringAsync($"{_provider.Url}/status");

        Assert.Equal("available", body);
    }

    public void Dispose() => _provider.Stop();
}
```

Namespaces: `WireMock.Server`, `WireMock.RequestBuilders`, `WireMock.ResponseBuilders`.

An integration test of an adapter sets the base URL in the host's configuration:

```csharp
var factory = new WebApplicationFactory<Program>().WithWebHostBuilder(builder =>
    builder.UseSetting("<the adapter's base-url key>", provider.Url));
```

A refusal is an arranged status (`WithStatusCode(402)`), a timeout an arranged delay longer than the
adapter's (`WithDelay(...)`).

## Checked

On a fresh Spring Boot 4 Gradle project (Java 21, `org.wiremock:wiremock-standalone` 3.13.2) and a fresh
.NET 10 xUnit project (`WireMock.Net` 2.18.0): the smoke test green, red against a changed arranged
answer, green again.
