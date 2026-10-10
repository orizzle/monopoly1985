# Guide to the reconstructed source

The source in `src/` is a reconstruction of the 1985 freeware Monopoly game for MS-DOS. It was decompiled from the original binaries and checked by recompiling. Compiled with Turbo Pascal 3 and moved onto the 1985 runtime, it reproduces `MONOPOLY.COM`, `MONOCODE.CHN` and `MONOCODE.000` byte for byte.

**About the names.** A compiled program does not keep identifiers or comments, so every name in this source was chosen during the reconstruction; none is the original author's. Each procedure header comment gives the procedure's address in the original program, and each global's comment gives its address in the original data segment (DS). Those addresses are facts; the names are interpretations.

## Program structure

- **`MONOPOLY.PAS` → `MONOPOLY.COM`, the loader.** `CheckAndChain` checks that `MONOGRAF.GRA`, `MONOCODE.CHN` and `MONOCODE.000` can be opened. If one is missing it shows the "Monopoly Problem" box; otherwise it `Chain`s to `MONOCODE.CHN`. The loader is compiled with minimum code and data segment sizes of `$0C72`/`$05CE`, the sizes of the chained game.
- **`MONOCODE.PAS` with `MONOCOD1.INC` and `MONOCOD2.INC` → `MONOCODE.CHN` and `MONOCODE.000`, the game.** It includes Borland's `GRAPH.P`, whose `GRAPH.BIN` code becomes part of the chain file. Four overlay procedures (`LandOnProperty`, `StartGame`, `SettleBankruptcy`, `SaveGameOvl`) form one overlay group, which goes into `MONOCODE.000`.
  - Two small wrappers, `GoBankrupt` and `SaveGame`, call overlays 3 and 4. They are declared `forward` earlier in the source, so procedures compiled before the overlay group can call them.

## Data model

**Typed constants** (stored in the code segment):

| Constant | Contents |
|---|---|
| `Group[1..10]` | The colour groups, including the railroads (9) and utilities (10): name, member squares, colours and house cost. Its `NextBuild` field is *written* at run time; it rotates which member gets the next house, and it is saved with the game. |
| `Square[1..40]` | The board squares: name, kind (street, railroad, utility, other), group, and the short names used for input and the holdings display. |
| `Deed[1..40]` | Prices and rents. |
| `TokenOfs[1..4,1..8]` | Per-player offsets that stop the tokens from overlapping. |
| `ChestCards`, `ChanceCards` | The 16 card texts of each deck, 5 lines each. |

**Global variables:**

| Variable | Contents |
|---|---|
| `Player[1..4]` (`PlayerRec`) | Name, location, cash, jail state and Get Out of Jail Free cards, bankruptcy and bank loan. |
| `Prop[1..40]` (`PropRec`) | Owner (0 = bank), mortgage flag, houses (5 = hotel). |
| `Gfx` (`GfxData`) | The contents of `MONOGRAF.GRA`, read in one piece: the board picture, dice faces, shaking-dice pictures and four token pictures per player. |
| `ChanceDeck`, `ChestDeck` | The shuffled card order. `ChanceIndex` and `ChestIndex` hold the last card drawn. |
| `Amount`, `Payer`, `Payee` | Every payment goes through `PayAmount` (Payer pays Amount) and `ReceiveAmount` (Payee receives Amount). |
| `SaveBuf` (`SaveRec`) | The saved-game record, 9128 bytes, written to and read from the save file in one piece. |

The rest are flags and temporaries, described in the `var` section of `MONOCODE.PAS`.

## Turn flow (main program)

1. `StartGame` (overlay 2) shows the title, then either reads the player names or loads a saved game (F2).
2. The main loop moves on to the next player who is not bankrupt. A player with a bank loan first goes to `RepayLoan`.
3. A player in jail goes to `JailTurn`: pay, roll for doubles, or use a card. Otherwise the turn goes to `DiceRoll`:
   - the dice shake until a key is pressed (F1 toggles sound, F2 saves);
   - `RollDice`;
   - `MoveToken`. A third double in a row goes to `ThreeDoubles` and then `GoToJail`.
4. The square the token lands on decides what happens next:

   | Square | Handled by |
   |---|---|
   | Property, railroad or utility | `PropertySquare` → `LandOnProperty` (buy, auction, rent) |
   | Community Chest | `CommunityChest` |
   | Chance | `Chance` |
   | Income Tax, Luxury Tax, Go To Jail | `TaxSquare` |
   | GO, jail, Free Parking | `CornerSquare` |

   A card that moves the token sets `MovedAgain`, and the new square is evaluated again.
5. `BusinessOrGo` offers the `BusinessMenu`: buy from or sell to a player, buy or return houses, view a deed, mortgage or unmortgage.
6. A player who cannot pay goes to `NotEnoughCash`. The options there are raising money through the business menu, a bank loan when it is not their turn, or leaving the game. Overlay 3 (`SettleBankruptcy`) then hands the player's property to the creditor or auctions it, and declares the winner when one player is left.

## Procedures

| Name | Original | Purpose |
|---|---|---|
| `ShuffleDecks` | P_4C33 | shuffles the Chance and Community Chest decks |
| `LoadGraphics` | P_4D53 | reads MONOGRAF.GRA into Gfx |
| `StepSound` | P_4DA4 | short falling chirp (token steps, houses) |
| `CornerSound` | P_4DED | rising sweep when a token reaches a corner |
| `ShowTurnGfx` | P_4E42 | "<name>'s turn" title on the graphics screen |
| `RattleSound` | P_4F74 | dice rattle clicks |
| `CalcTokenXY` | P_4FCB | screen position of the current player's token |
| `FlashToken` | P_513C | flashes the current token with beeps |
| `BlinkToken` | P_5215 | flashes the current token silently |
| `GoToJail` | P_52DB | jail siren, token to square 11, player in jail |
| `ThreeDoubles` | P_54AF | third double in a row: siren, then GoToJail |
| `ShakeDice` | P_5614 | one frame of the shaking-dice animation |
| `RollDice` | P_567D | throws the dice, shows them, counts doubles |
| `NotEnoughCash` | P_5749 | Payer cannot pay: raise money, bank loan or out of the game |
| `ShowCashGfx` | P_5AB2 | player names and cash under the graphics board |
| `ShowPanels` | P_5BBA | player name/cash panels (text mode) |
| `ShowHoldings` | P_5D5D | short names of every player's properties |
| `ShowBoard` | P_5E87 | graphics mode with the board picture |
| `CountDownGfx` | P_5EDC | Payer pays Amount, counted down on the graphics screen |
| `CountUpGfx` | P_5FA0 | Payee receives Amount, counted up on the graphics screen |
| `PayAmount` | P_6064 | Payer pays Amount (checks for insufficient cash) |
| `ReceiveAmount` | P_6234 | Payee receives Amount |
| `PassGo` | P_63AA | collect $200 for passing GO |
| `StepToken` | P_63CD | moves the current token one square |
| `SelectDeed` | P_64BB | sets DeedSquare and the deed card colours |
| `TitleBox` | P_6544 | title box with "Monopoly" and a subtitle |
| `MoveToken` | P_6620 | moves the token MoveCount squares and names the square |
| `DiceRoll` | P_670D | shake the dice until a key (F1 sound, F2 save), roll and move |
| `CheckMonopoly` | P_6816 | is colour group CheckGroup owned by one player? |
| `CalcInterest` | P_691E | mortgage interest of SelProp (10% of the mortgage value) |
| `ShowHouses` | P_6959 | houses/hotel of DeedSquare on the deed card |
| `ShowDeed` | P_6AB6 | title deed card of DeedSquare |
| `WriteTurn` | P_7064 | "<name>'s turn" in the current window |
| `OpenTurnWindow` | P_715A | blue message window with the turn title |
| `OpenStatusWindow` | P_71EA | green window with the player's position and amount due |
| `OpenAskWindow` | P_73DD | small window for the business/go-on question |
| `SelectPlayer` | P_7443 | asks for a player name, sets SelPlayer (0 = cancelled) |
| `WaitKey` | P_7680 | "<Press Any Key>" and waits (key is not read) |
| `Message3` | P_76C5 | three message lines, a beep, WaitKey |
| `GetNumber` | P_773B | converts Answer to AnswerVal; -1 = cancelled |
| `SelectProperty` | P_77D9 | asks for a property short name, sets SelProp |
| `MortgageInterest` | P_8268 | interest when a mortgaged property changes hands |
| `BuyFromPlayer` | P_8633 | business: buy a property from another player |
| `SellToPlayer` | P_888C | business: sell a property to another player |
| `Unmortgage` | P_8BBD | business: lift a mortgage |
| `Mortgage` | P_8D3B | business: mortgage a property |
| `ChooseGroup` | P_8E2F | asks for a colour group to build on/return from (ChosenGroup) |
| `ReturnHouses` | P_9674 | business: sell houses/hotels back to the bank |
| `BuyHouses` | P_9B2C | business: buy houses/hotels |
| `ViewDeed` | P_A1B3 | business: show a title deed card |
| `BusinessMenu` | P_A1FB | the business menu |
| `BuyFromBank` | P_A578 | buy the unowned square the player is on |
| `AuctionSquare` | P_A615 | auction the square the player is on |
| `BusinessOrGo` | P_A8B6 | "Business or Go on?" at the end of a turn |
| `AlertKey` | P_A9CF | red window, low beep, waits for a key |
| `OpenBankruptWindow` | P_AA52 | clears the screen for the bankruptcy messages |
| `LandOnProperty` | overlay 1 | overlay 1: buy, auction or pay rent |
| `StartGame` | overlay 2 | overlay 2: title screen, player entry, loading a saved game |
| `SettleBankruptcy` | overlay 3 | overlay 3: bankruptcy of Debtor, end of the game |
| `SaveGameOvl` | overlay 4 | overlay 4: save the game to disk |
| `GoBankrupt` | P_B6DF | calls overlay 3 |
| `SaveGame` | P_B6FC | calls overlay 4 |
| `DrawCard` | P_CE39 | draws the current card (CardTitle, CardLine) |
| `ShowCard` | P_CFC4 | shows the card and waits for a key |
| `CardToBoard` | P_D03B | back to the board screen with the card title |
| `CardAdvance` | P_D0A6 | card moves the token MoveCount squares |
| `RedrawText` | P_D0CC | clears the text screen, holdings and panels |
| `CardGoToJail` | P_D107 | "Go to jail" card |
| `RedrawStatus` | P_D130 | redraws holdings and panels after a card |
| `GiveJailCard` | P_D175 | adds a Get Out of Jail Free card |
| `Message4` | P_D2A9 | card result message |
| `CommunityChest` | P_D317 | draws and carries out a Community Chest card |
| `Chance` | P_D997 | draws and carries out a Chance card |
| `PropertySquare` | P_E258 | landed on a property, railroad or utility |
| `CornerSquare` | P_E2A8 | landed on GO, jail or Free Parking |
| `TaxSquare` | P_E387 | Income Tax, Luxury Tax, Go To Jail |
| `OpenLoanWindow` | P_E8FA | window for the bank-loan messages |
| `RepayLoan` | P_E99C | player must repay the bank loan first |
| `JailTurn` | P_EBAB | turn of a player in jail: pay, roll or use a card |

## Behaviour of the original that the source reproduces

- **Shaking-dice picture index.** `ShakeDice` draws `Gfx.Shake[Random(8)]`. `Random(8)` returns 0..7 but the array is `1..7`, so index 0 reads the 636 bytes just before the array: the dice-face pictures and the end of the board picture.
- **No `Randomize`.** The random generator starts from the runtime's initial seed every time. What makes games differ is player timing: `Random` is called on every frame of the shaking-dice animation and of the player-name entry loop, until a key is pressed.
- **Keys typed during screen output are lost.** Both programs have the runtime's Ctrl-C/Ctrl-S checking turned on (a flag in the program header). After every character it writes, the Turbo Pascal runtime reads any waiting key and throws it away; Ctrl-S pauses the output instead.
- **Real arithmetic.** The literal `0.1` in `CalcInterest` is stored truncated, as `7D CC CC CC CC 4C`, slightly below 0.1. As a result, `Round(Price / 2 * 0.1)` is 7, not 8, for a $150 property.
- **Sound timing depends on the CPU.** Several sound effects are loops of `Sound` calls with no `Delay`:
  - the token-step chirp, the corner sweep and the house sweeps;
  - the jail siren and the three-doubles siren, which compute `Trunc(x / 2)` with software floating point.

  On a 4.77 MHz IBM PC these take tenths of a second to several seconds. On faster machines they are shorter.
- **Run-time error that cannot be triggered in practice.** `ShowTurnGfx` and `WriteTurn` call `Copy(Name, Length(Name), 1)`, which would stop with run-time error 11 on an empty name. Name entry never accepts an empty name, so this cannot happen.
- **Saving ends the program.** Saving a game (F2 during the dice roll) writes the whole `SaveBuf`, including the 8700-byte board picture with the tokens on it, then halts. Loading restores everything, including the board picture.
