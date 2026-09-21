<!-- Model B memory template (cross-project Java language reference). Imported 2026-09-21 from the user's global memory (maven-best-practices.md) by ruling: PRD §D5's global tier has no Pi home, so language refs ride the stack's memory templates and are scaffolded into <project>/docs/memory/. -->

# Maven Best Practices for Java Library Projects

## Build Lifecycle Management

### Critical Build Rules

**ALWAYS run clean before important builds:**
```bash
# ✅ CORRECT - Clean build before commit/release
./mvnw clean compile
./mvnw clean test
./mvnw clean install

# ❌ WRONG - Incremental builds can hide issues
./mvnw compile  # May use stale cached files
```

**Why Clean Builds Matter:**
- Incremental builds with "Nothing to compile" can hide breaking changes
- Stale cached class files mask compilation errors
- Refactored/removed methods may appear to work due to old binaries
- Clean build exposes real compilation state

### Maven Build Phases (Ordered)

```
validate → compile → test → package → verify → install → deploy
```

**Common Commands:**
```bash
# Compile only
./mvnw clean compile

# Compile and run unit tests
./mvnw clean test

# Run integration tests (includes unit tests)
./mvnw clean verify

# Install to local Maven repository
./mvnw clean install

# Deploy to remote repository
./mvnw clean deploy
```

### Branch-Specific Build Rules (CRITICAL)

**Maven install/deploy ONLY from master branch:**

```bash
# ✅ CORRECT - Build releases from master
git checkout master
./mvnw clean install

# ❌ WRONG - NEVER from develop or feature branches
git checkout develop
./mvnw clean install  # DON'T DO THIS

git checkout feature/xyz
./mvnw clean install  # DON'T DO THIS
```

**Why:**
- Master is production branch
- Tagged versions must be built from master
- Ensures artifact version matches git tag
- Prevents accidental snapshot deployments to repositories

**Exception:** Local development testing on feature branches is OK, but never deploy

### Build Verification Workflow

**Before every commit:**
```bash
# 1. Clean build
./mvnw clean compile

# 2. Verify exit code
echo $?  # Should be 0

# 3. Run tests
./mvnw test

# 4. Commit only if GREEN
git commit -m "Your message"
```

## Dependency Management

### Version Management

**Use properties for version management:**
```xml
<properties>
    <quarkus.version>3.28.1</quarkus.version>
    <junit.version>5.10.1</junit.version>
    <mockito.version>5.7.0</mockito.version>
</properties>

<dependencies>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-core</artifactId>
        <version>${quarkus.version}</version>
    </dependency>
</dependencies>
```

**Benefits:**
- Single place to update versions
- Consistency across modules
- Easier dependency upgrades

### Dependency Scopes

**Use appropriate scopes:**
```xml
<!-- Compile scope - default, needed at compile and runtime -->
<dependency>
    <groupId>org.example</groupId>
    <artifactId>library</artifactId>
    <version>1.0.0</version>
</dependency>

<!-- Test scope - only for tests -->
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>${junit.version}</version>
    <scope>test</scope>
</dependency>

<!-- Provided scope - available at compile but not packaged -->
<dependency>
    <groupId>jakarta.servlet</groupId>
    <artifactId>jakarta.servlet-api</artifactId>
    <version>6.0.0</version>
    <scope>provided</scope>
</dependency>

<!-- Runtime scope - not needed for compilation -->
<dependency>
    <groupId>org.postgresql</groupId>
    <artifactId>postgresql</artifactId>
    <version>42.7.0</version>
    <scope>runtime</scope>
</dependency>
```

### Dependency Management Section

**For library projects coordinating versions:**
```xml
<dependencyManagement>
    <dependencies>
        <!-- Define versions here, actual deps in modules -->
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-bom</artifactId>
            <version>${quarkus.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

**Usage in child modules:**
```xml
<dependencies>
    <!-- Version inherited from parent's dependencyManagement -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-core</artifactId>
    </dependency>
</dependencies>
```

### Transitive Dependencies

**Exclude unwanted transitive dependencies:**
```xml
<dependency>
    <groupId>org.example</groupId>
    <artifactId>library</artifactId>
    <version>1.0.0</version>
    <exclusions>
        <exclusion>
            <groupId>commons-logging</groupId>
            <artifactId>commons-logging</artifactId>
        </exclusion>
    </exclusions>
</dependency>
```

**Analyze dependency tree:**
```bash
# View full dependency tree
./mvnw dependency:tree

# Find specific dependency
./mvnw dependency:tree | grep "artifact-name"

# View conflicts
./mvnw dependency:tree -Dverbose
```

## Plugin Configuration

### Compiler Plugin (CRITICAL)

**Always specify Java version explicitly:**
```xml
<properties>
    <maven.compiler.source>21</maven.compiler.source>
    <maven.compiler.target>21</maven.compiler.target>
    <maven.compiler.release>21</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
</properties>

<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <version>3.11.0</version>
            <configuration>
                <release>21</release>
                <compilerArgs>
                    <arg>-parameters</arg>
                    <arg>-Xlint:unchecked</arg>
                    <arg>-Xlint:deprecation</arg>
                </compilerArgs>
            </configuration>
        </plugin>
    </plugins>
</build>
```

**Why:**
- Prevents "source/target mismatch" issues
- Ensures consistent compilation across environments
- Enables Java 21+ features
- `-parameters` flag preserves parameter names for reflection

### Surefire Plugin (Unit Tests)

**Configure for reliable test execution:**
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <version>3.2.3</version>
    <configuration>
        <!-- Run tests in parallel -->
        <parallel>methods</parallel>
        <threadCount>4</threadCount>
        
        <!-- Proper test output -->
        <printSummary>true</printSummary>
        <useFile>true</useFile>
        
        <!-- Include/exclude patterns -->
        <includes>
            <include>**/*Test.java</include>
        </includes>
        <excludes>
            <exclude>**/*IT.java</exclude>
        </excludes>
        
        <!-- JVM arguments -->
        <argLine>
            -Xmx1024m
            -XX:+EnableDynamicAgentLoading
        </argLine>
    </configuration>
</plugin>
```

### Failsafe Plugin (Integration Tests)

**Separate integration tests from unit tests:**
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-failsafe-plugin</artifactId>
    <version>3.2.3</version>
    <configuration>
        <includes>
            <include>**/*IT.java</include>
        </includes>
        <classesDirectory>${project.build.outputDirectory}</classesDirectory>
    </configuration>
    <executions>
        <execution>
            <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

**Usage:**
```bash
# Run only unit tests
./mvnw test

# Run integration tests (includes unit tests)
./mvnw verify
```

### JAR Plugin (Library Packaging)

**Create proper JAR with manifest:**
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-jar-plugin</artifactId>
    <version>3.3.0</version>
    <configuration>
        <archive>
            <manifest>
                <addDefaultImplementationEntries>true</addDefaultImplementationEntries>
                <addDefaultSpecificationEntries>true</addDefaultSpecificationEntries>
            </manifest>
            <manifestEntries>
                <Built-By>${user.name}</Built-By>
                <Build-Time>${maven.build.timestamp}</Build-Time>
            </manifestEntries>
        </archive>
    </configuration>
</plugin>
```

### Source Plugin (CRITICAL for Libraries)

**Always attach sources:**
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-source-plugin</artifactId>
    <version>3.3.0</version>
    <executions>
        <execution>
            <id>attach-sources</id>
            <goals>
                <goal>jar-no-fork</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

**Why:**
- IDE can show source code for library
- Easier debugging for consumers
- Professional library standard

### Javadoc Plugin (CRITICAL for Libraries)

**Generate API documentation:**
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-javadoc-plugin</artifactId>
    <version>3.6.3</version>
    <configuration>
        <source>21</source>
        <doclint>none</doclint>
        <quiet>true</quiet>
    </configuration>
    <executions>
        <execution>
            <id>attach-javadocs</id>
            <goals>
                <goal>jar</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

**Generate standalone docs:**
```bash
./mvnw javadoc:javadoc
# Output: target/site/apidocs/
```

## Library Project Specific Practices

### Minimal Dependencies

**Keep dependency footprint small:**
```xml
<!-- ✅ GOOD - Only essential dependencies -->
<dependencies>
    <dependency>
        <groupId>org.slf4j</groupId>
        <artifactId>slf4j-api</artifactId>
        <version>2.0.9</version>
    </dependency>
</dependencies>

<!-- ❌ BAD - Pulling in entire frameworks -->
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter</artifactId>
        <version>3.2.0</version>
    </dependency>
</dependencies>
```

**Why:**
- Libraries should not dictate frameworks to consumers
- Smaller dependency tree = fewer conflicts
- Faster builds and smaller artifacts

### Optional Dependencies

**Use optional for non-essential features:**
```xml
<dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
    <version>2.16.0</version>
    <optional>true</optional>
</dependency>
```

**When to use optional:**
- Feature only works with specific libraries
- Consumer can choose alternative implementations
- Not required for core functionality

### Shading (Use Sparingly)

**Only shade if absolutely necessary:**
```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-shade-plugin</artifactId>
    <version>3.5.1</version>
    <executions>
        <execution>
            <phase>package</phase>
            <goals>
                <goal>shade</goal>
            </goals>
            <configuration>
                <relocations>
                    <relocation>
                        <pattern>com.google.common</pattern>
                        <shadedPattern>mylib.shaded.guava</shadedPattern>
                    </relocation>
                </relocations>
            </configuration>
        </execution>
    </executions>
</plugin>
```

**When to shade:**
- Avoid version conflicts with consumer dependencies
- Internalize implementation details
- Create fat JARs for standalone tools

**Caution:**
- Increases JAR size
- Complicates debugging
- Last resort solution

## Version Management

### Semantic Versioning (REQUIRED)

**Use MAJOR.MINOR.PATCH format:**
```xml
<version>1.2.3</version>
```

**Rules:**
- **MAJOR:** Breaking API changes
- **MINOR:** New features, backward compatible
- **PATCH:** Bug fixes, backward compatible

**SNAPSHOT versions for development:**
```xml
<version>1.3.0-SNAPSHOT</version>
```

### Versions Plugin

**Check for updates:**
```bash
# Check dependency updates
./mvnw versions:display-dependency-updates

# Check plugin updates
./mvnw versions:display-plugin-updates

# Update to latest versions (carefully!)
./mvnw versions:use-latest-versions
```

## Build Profiles

### Environment-Specific Profiles

**Separate dev, test, and production configs:**
```xml
<profiles>
    <profile>
        <id>dev</id>
        <activation>
            <activeByDefault>true</activeByDefault>
        </activation>
        <properties>
            <skipTests>false</skipTests>
        </properties>
    </profile>
    
    <profile>
        <id>production</id>
        <properties>
            <skipTests>false</skipTests>
        </properties>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-enforcer-plugin</artifactId>
                    <executions>
                        <execution>
                            <id>enforce-no-snapshots</id>
                            <goals>
                                <goal>enforce</goal>
                            </goals>
                            <configuration>
                                <rules>
                                    <requireReleaseDeps>
                                        <message>No Snapshots Allowed in Production!</message>
                                    </requireReleaseDeps>
                                </rules>
                            </configuration>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>
    
    <profile>
        <id>quick</id>
        <properties>
            <skipTests>true</skipTests>
            <maven.javadoc.skip>true</maven.javadoc.skip>
        </properties>
    </profile>
</profiles>
```

**Usage:**
```bash
# Use specific profile
./mvnw clean install -Pproduction

# Quick build without tests
./mvnw clean install -Pquick
```

## Performance Optimization

### Parallel Builds

**Enable parallel execution:**
```bash
# Build with multiple threads
./mvnw clean install -T 4

# Use number of CPU cores
./mvnw clean install -T 1C
```

**Configure in pom.xml:**
```xml
<properties>
    <maven.build.threads>4</maven.build.threads>
</properties>
```

### Build Cache (Maven 3.9+)

**Enable incremental builds:**
```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <configuration>
                <useIncrementalCompilation>true</useIncrementalCompilation>
            </configuration>
        </plugin>
    </plugins>
</build>
```

### Skip Unnecessary Steps

**During development:**
```bash
# Skip tests for quick compile check
./mvnw clean compile -DskipTests

# Skip integration tests only
./mvnw clean install -DskipITs

# Skip Javadoc generation
./mvnw clean install -Dmaven.javadoc.skip=true
```

**NEVER skip tests before commit/release!**

## Multi-Module Projects

### Parent POM Structure

```xml
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>parent</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    
    <modules>
        <module>core</module>
        <module>api</module>
        <module>impl</module>
    </modules>
    
    <dependencyManagement>
        <!-- Shared dependency versions -->
    </dependencyManagement>
    
    <build>
        <pluginManagement>
            <!-- Shared plugin configs -->
        </pluginManagement>
    </build>
</project>
```

### Module Dependency Order

**Build order matters:**
```xml
<modules>
    <module>api</module>        <!-- No dependencies -->
    <module>core</module>        <!-- Depends on api -->
    <module>impl</module>        <!-- Depends on core -->
    <module>integration</module> <!-- Depends on all -->
</modules>
```

**Maven resolves build order automatically**

### Reactor Build Commands

```bash
# Build entire project
./mvnw clean install

# Build specific module and dependencies
./mvnw clean install -pl impl -am

# Build from specific module onward
./mvnw clean install -rf core

# Build specific module only
./mvnw clean install -pl api
```

## Repository Configuration

### Distribution Management

**Configure deployment targets:**
```xml
<distributionManagement>
    <repository>
        <id>releases</id>
        <name>Internal Releases</name>
        <url>https://repo.example.com/releases</url>
    </repository>
    
    <snapshotRepository>
        <id>snapshots</id>
        <name>Internal Snapshots</name>
        <url>https://repo.example.com/snapshots</url>
    </snapshotRepository>
</distributionManagement>
```

### Settings.xml Configuration

**Store credentials in ~/.m2/settings.xml:**
```xml
<settings>
    <servers>
        <server>
            <id>releases</id>
            <username>${env.REPO_USERNAME}</username>
            <password>${env.REPO_PASSWORD}</password>
        </server>
        
        <server>
            <id>snapshots</id>
            <username>${env.REPO_USERNAME}</username>
            <password>${env.REPO_PASSWORD}</password>
        </server>
    </servers>
</settings>
```

**NEVER commit credentials to pom.xml!**

## Common Issues and Solutions

### Issue: "Package does not exist"

**Cause:** Stale compilation cache

**Solution:**
```bash
./mvnw clean compile
```

### Issue: Tests passing locally, failing in CI

**Cause:** Different Maven/Java versions or stale test cache

**Solution:**
```bash
# Force clean test
./mvnw clean test

# Check versions
./mvnw --version
java -version
```

### Issue: "Cannot resolve dependencies"

**Cause:** Offline mode or repository issues

**Solution:**
```bash
# Force online mode
./mvnw clean install -U

# Check effective POM
./mvnw help:effective-pom

# Check dependency tree
./mvnw dependency:tree
```

### Issue: "OutOfMemoryError during build"

**Solution:**
```bash
# Set Maven opts
export MAVEN_OPTS="-Xmx2048m -XX:MaxPermSize=512m"

# Or in .mvn/jvm.config
echo "-Xmx2048m" > .mvn/jvm.config
```

### Issue: "NoClassDefFoundError at runtime"

**Cause:** Dependency with wrong scope

**Solution:**
```xml
<!-- Change from test/provided to compile -->
<dependency>
    <groupId>org.example</groupId>
    <artifactId>library</artifactId>
    <version>1.0.0</version>
    <!-- Remove or change scope -->
</dependency>
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Test

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up JDK 21
      uses: actions/setup-java@v4
      with:
        java-version: '21'
        distribution: 'temurin'
        cache: 'maven'
    
    - name: Build with Maven
      run: ./mvnw clean verify
    
    - name: Publish Test Results
      uses: dorny/test-reporter@v1
      if: always()
      with:
        name: Test Results
        path: '**/surefire-reports/*.xml'
        reporter: java-junit
```

### Release Workflow

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up JDK 21
      uses: actions/setup-java@v4
      with:
        java-version: '21'
        distribution: 'temurin'
        cache: 'maven'
    
    - name: Build and Deploy
      run: ./mvnw clean deploy -Pproduction
      env:
        REPO_USERNAME: ${{ secrets.REPO_USERNAME }}
        REPO_PASSWORD: ${{ secrets.REPO_PASSWORD }}
```

## Best Practices Checklist

### Before Every Commit
- [ ] Run `./mvnw clean compile` (verify no compilation errors)
- [ ] Run `./mvnw test` (verify all tests pass)
- [ ] Remove unused imports from Java files
- [ ] Run tests again after import cleanup
- [ ] Verify exit codes are 0

### Before Every Release
- [ ] Update version in pom.xml (remove -SNAPSHOT)
- [ ] Run `./mvnw clean verify` (full test suite)
- [ ] Check dependency updates (`./mvnw versions:display-dependency-updates`)
- [ ] Verify sources JAR generated
- [ ] Verify Javadoc JAR generated
- [ ] Update CHANGELOG.md
- [ ] Build from master branch ONLY
- [ ] Tag release after successful build
- [ ] Push tags to remote

### Library Project Standards
- [ ] Minimal dependencies (keep it lean)
- [ ] Proper scope for all dependencies
- [ ] Sources and Javadoc attached
- [ ] Semantic versioning followed
- [ ] No SNAPSHOT dependencies in releases
- [ ] README with usage examples
- [ ] Clean public API (minimal exposed classes)

### Multi-Module Projects
- [ ] Consistent versioning across modules
- [ ] Shared dependency versions in parent
- [ ] Proper module build order
- [ ] Integration tests in separate module
- [ ] No circular dependencies

## Memory Triggers

**BEFORE building:**
1. "Is this a release build?" → Checkout master, run clean install
2. "Have I made code changes?" → Run clean compile first
3. "Are tests passing?" → Run full test suite
4. "Is this a library?" → Verify sources/javadoc attached

**BEFORE committing:**
1. "Did I run clean compile?" → Required before every commit
2. "Are tests GREEN?" → Never commit RED state
3. "Any unused imports?" → Clean them up

**BEFORE releasing:**
1. "Am I on master branch?" → REQUIRED for releases
2. "Is version correct?" → Update and remove -SNAPSHOT
3. "Are all tests passing?" → Run clean verify
4. "Documentation updated?" → CHANGELOG, README, Implementation.md
