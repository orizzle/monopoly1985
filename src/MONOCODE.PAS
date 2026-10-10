program MonoCode;
{$I GRAPH.P}

type
  Str5 = string[5];
  Str30 = string[30];
  Str36 = string[36];
  GroupRec = record                   { colour group, 35 bytes }
    Name: string[12];
    Size: integer;                    { number of properties }
    Member: array[1..4] of integer;   { their squares }
    TextCol, BackCol: integer;        { colours of the group }
    InfoText, InfoBack: integer;      { colours of the deed card's rent table }
    HouseCost: integer;
    NextBuild: integer;               { member that gets the next house (written at run time) }
  end;
  SquareRec = record                  { board square, 42 bytes }
    Name: string[22];
    Kind: byte;                       { 0 street, 1 railroad, 2 utility, 3 other }
    Grp: integer;                     { colour group (Group) }
    Col, Row: integer;                { position of the short name in the holdings list }
    Abbr, AbbrUp: Str5;               { short name, as shown and as typed }
  end;
  DeedRec = record                    { title deed, 15 bytes }
    Price: integer;
    NoBuild: byte;                    { 3 = cannot be built on }
    Rent: array[0..5] of integer;     { rent with 0..4 houses, hotel }
  end;
  PlayerRec = record                  { 34 bytes }
    Name: string[10];                 {  0  as typed }
    Loc: integer;                     { 11  square 1..40 }
    Cash: integer;                    { 13 }
    InJail: boolean;                  { 15 }
    JailCards: integer;               { 16  Get Out of Jail Free cards }
    JailTurns: integer;               { 18  rolls made in jail }
    Bankrupt: boolean;                { 20 }
    UName: string[10];                { 21  name in capitals }
    Loan: integer;                    { 32  bank loan to repay }
  end;
  PropRec = record                    { state of a square, 5 bytes }
    Owner: integer;                   { player, 0 = bank }
    Mortgaged: boolean;
    Houses: integer;                  { 5 = hotel }
  end;
  BoardPic = array[1..8700] of byte;
  GfxData = record                    { 13774 bytes = contents of MONOGRAF.GRA }
    Board: BoardPic;                              { DS:02C9  board (GetPic/PutPic) }
    Dice: array[1..6] of array[1..61] of byte;    { DS:24C5  dice faces }
    Shake: array[1..7] of array[1..636] of byte;  { DS:2633  shaking dice }
    Tok1, Tok2, Tok3, Tok4: array[1..4] of array[1..16] of byte;  { DS:3797.. tokens }
  end;
  SaveRec = record                    { saved game, 9128 bytes }
    SvPlayers: array[1..4] of PlayerRec;
    SvProp: array[1..40] of PropRec;
    SvNextBuild: array[1..8] of integer;
    SvChanceDeck, SvChestDeck: array[1..16] of integer;
    SvChestIndex, SvChanceIndex: integer;
    SvSoundOn: boolean;
    SvNumPlayers, SvCurPlayer, SvDoubles: integer;
    SvRepeatTurn: boolean;
    Board: BoardPic;
  end;
const
  Group: array[1..10] of GroupRec = (
    (Name:'DarkPurple'; Size:2; Member:(4,2,0,0); TextCol:1; BackCol:5; InfoText:15; InfoBack:7; HouseCost:50;
        NextBuild:1),
    (Name:'Cyan'; Size:3; Member:(10,9,7,0); TextCol:15; BackCol:3; InfoText:10; InfoBack:7; HouseCost:50; NextBuild:1),
    (Name:'LightPurple'; Size:3; Member:(15,14,12,0); TextCol:14; BackCol:5; InfoText:12; InfoBack:0;
        HouseCost:100; NextBuild:1),
    (Name:'Orange'; Size:3; Member:(20,19,17,0); TextCol:14; BackCol:6; InfoText:15; InfoBack:7; HouseCost:100;
        NextBuild:1),
    (Name:'Red'; Size:3; Member:(25,24,22,0); TextCol:15; BackCol:4; InfoText:15; InfoBack:7; HouseCost:150;
        NextBuild:1),
    (Name:'Yellow'; Size:3; Member:(30,28,27,0); TextCol:14; BackCol:7; InfoText:15; InfoBack:3; HouseCost:150;
        NextBuild:1),
    (Name:'Green'; Size:3; Member:(35,33,32,0); TextCol:14; BackCol:2; InfoText:10; InfoBack:7; HouseCost:200;
        NextBuild:1),
    (Name:'Blue'; Size:2; Member:(40,38,0,0); TextCol:15; BackCol:1; InfoText:15; InfoBack:7; HouseCost:200;
        NextBuild:1),
    (Name:'RR'; Size:4; Member:(6,16,26,36); TextCol:0; BackCol:7; InfoText:15; InfoBack:0; HouseCost:0; NextBuild:0),
    (Name:'Util'; Size:2; Member:(13,29,0,0); TextCol:15; BackCol:7; InfoText:1; InfoBack:3; HouseCost:0; NextBuild:0));

  Square: array[1..40] of SquareRec = (
    (Name:'GO'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Mediterranean Avenue'; Kind:0; Grp:1; Col:1; Row:1; Abbr:'Medit'; AbbrUp:'MEDIT'),
    (Name:'Community Chest'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Baltic Avenue'; Kind:0; Grp:1; Col:6; Row:1; Abbr:'Balt'; AbbrUp:'BALT'),
    (Name:'Income Tax'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Reading Railroad'; Kind:1; Grp:9; Col:1; Row:5; Abbr:'Rea'; AbbrUp:'REA'),
    (Name:'Oriental Avenue'; Kind:0; Grp:2; Col:10; Row:1; Abbr:'Ori'; AbbrUp:'ORI'),
    (Name:'Chance'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Vermont Avenue'; Kind:0; Grp:2; Col:13; Row:1; Abbr:'Ver'; AbbrUp:'VER'),
    (Name:'Connecticut Avenue'; Kind:0; Grp:2; Col:16; Row:1; Abbr:'Con'; AbbrUp:'CON'),
    (Name:'just visiting...'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'St. Charles Place'; Kind:0; Grp:3; Col:1; Row:2; Abbr:'StC'; AbbrUp:'STC'),
    (Name:'Electric Company'; Kind:2; Grp:10; Col:13; Row:5; Abbr:'Ele'; AbbrUp:'ELE'),
    (Name:'States Avenue'; Kind:0; Grp:3; Col:4; Row:2; Abbr:'Sta'; AbbrUp:'STA'),
    (Name:'Virginia Avenue'; Kind:0; Grp:3; Col:7; Row:2; Abbr:'Vir'; AbbrUp:'VIR'),
    (Name:'Pennsylvania Railroad'; Kind:1; Grp:9; Col:4; Row:5; Abbr:'Prr'; AbbrUp:'PRR'),
    (Name:'St. James Place'; Kind:0; Grp:4; Col:10; Row:2; Abbr:'StJ'; AbbrUp:'STJ'),
    (Name:'Community Chest'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Tennessee Avenue'; Kind:0; Grp:4; Col:13; Row:2; Abbr:'Ten'; AbbrUp:'TEN'),
    (Name:'New York Avenue'; Kind:0; Grp:4; Col:16; Row:2; Abbr:'New'; AbbrUp:'NEW'),
    (Name:'Free Parking'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Kentucky Avenue'; Kind:0; Grp:5; Col:1; Row:3; Abbr:'Ken'; AbbrUp:'KEN'),
    (Name:'Chance'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Indiana Avenue'; Kind:0; Grp:5; Col:4; Row:3; Abbr:'Ind'; AbbrUp:'IND'),
    (Name:'Illinois Avenue'; Kind:0; Grp:5; Col:7; Row:3; Abbr:'Ill'; AbbrUp:'ILL'),
    (Name:'B & O Railroad'; Kind:1; Grp:9; Col:7; Row:5; Abbr:'B&O'; AbbrUp:'B&O'),
    (Name:'Atlantic Avenue'; Kind:0; Grp:6; Col:10; Row:3; Abbr:'Atl'; AbbrUp:'ATL'),
    (Name:'Ventnor Avenue'; Kind:0; Grp:6; Col:13; Row:3; Abbr:'Ven'; AbbrUp:'VEN'),
    (Name:'Water Works'; Kind:2; Grp:10; Col:16; Row:5; Abbr:'Wat'; AbbrUp:'WAT'),
    (Name:'Marvin Gardens'; Kind:0; Grp:6; Col:16; Row:3; Abbr:'Mar'; AbbrUp:'MAR'),
    (Name:'GO TO JAIL'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Pacific Avenue'; Kind:0; Grp:7; Col:1; Row:4; Abbr:'Pac'; AbbrUp:'PAC'),
    (Name:'North Carolina Avenue'; Kind:0; Grp:7; Col:4; Row:4; Abbr:'Nor'; AbbrUp:'NOR'),
    (Name:'Community Chest'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Pennsylvania Avenue'; Kind:0; Grp:7; Col:7; Row:4; Abbr:'Pen'; AbbrUp:'PEN'),
    (Name:'Short Line Railroad'; Kind:1; Grp:9; Col:10; Row:5; Abbr:'Sho'; AbbrUp:'SHO'),
    (Name:'Chance'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Park Place'; Kind:0; Grp:8; Col:10; Row:4; Abbr:'Park'; AbbrUp:'PARK'),
    (Name:'Luxury Tax'; Kind:3; Grp:0; Col:0; Row:0; Abbr:''; AbbrUp:''),
    (Name:'Boardwalk'; Kind:0; Grp:8; Col:14; Row:4; Abbr:'Board'; AbbrUp:'BOARD'));

  TokenOfs: array[1..4,1..8] of integer = (
    (1,3,-3,3,-3,-1,1,-1),
    (-3,3,-3,-1,1,-1,1,3),
    (1,-1,1,3,-3,3,-3,-1),
    (-3,-1,1,-1,1,3,-3,3));

  Deed: array[1..40] of DeedRec = (
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:60; NoBuild:0; Rent:(2,10,30,90,160,250)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:60; NoBuild:0; Rent:(4,20,60,180,320,450)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:200; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:100; NoBuild:0; Rent:(6,30,90,270,400,550)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:100; NoBuild:0; Rent:(6,30,90,270,400,550)),
    (Price:120; NoBuild:0; Rent:(8,40,100,300,450,600)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:140; NoBuild:0; Rent:(10,50,150,450,625,750)),
    (Price:150; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:140; NoBuild:0; Rent:(10,50,150,450,625,750)),
    (Price:160; NoBuild:0; Rent:(12,60,180,500,700,900)),
    (Price:200; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:180; NoBuild:0; Rent:(14,70,200,550,750,950)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:180; NoBuild:0; Rent:(14,70,200,550,750,950)),
    (Price:200; NoBuild:0; Rent:(16,80,220,600,800,1000)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:220; NoBuild:0; Rent:(18,90,250,700,875,1050)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:220; NoBuild:0; Rent:(18,90,250,700,875,1050)),
    (Price:240; NoBuild:0; Rent:(20,100,300,750,925,1100)),
    (Price:200; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:260; NoBuild:0; Rent:(22,110,330,800,975,1150)),
    (Price:260; NoBuild:0; Rent:(22,110,330,800,975,1150)),
    (Price:150; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:280; NoBuild:0; Rent:(24,120,360,850,1025,1200)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:300; NoBuild:0; Rent:(26,130,390,900,1100,1275)),
    (Price:300; NoBuild:0; Rent:(26,130,390,900,1100,1275)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:320; NoBuild:0; Rent:(28,150,450,1000,1200,1400)),
    (Price:200; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:350; NoBuild:0; Rent:(35,175,500,1100,1300,1500)),
    (Price:0; NoBuild:3; Rent:(0,0,0,0,0,0)),
    (Price:400; NoBuild:0; Rent:(50,200,600,1400,1700,2000)));


var
  { Globals in declaration order; the comment gives the address in the original data segment. }
  ChosenGroup: integer;               { DS:0260  colour group chosen in ChooseGroup }
  CurPlayer: integer;                 { DS:0262 }
  Die1, Die2: integer;                { DS:0264 }
  MoveCount: integer;                 { DS:0268  dice total / squares to move }
  I, J, K: integer;                   { DS:026A  loop variables }
  TokenX, TokenY: integer;            { DS:0270  token position on the graphics screen }
  NameInput: string[10];              { DS:0274  player name being typed }
  Answer: Str5;                       { DS:027F  number typed by the player }
  AnswerVal, ValCode: integer;        { DS:0285 }
  Msg, Msg2: Str30;                   { DS:0289 }
  TaxChoice: char;                    { DS:02C7 }
  Key: char;                          { DS:02C8  last key read }
  Gfx: GfxData;                       { DS:02C9  MONOGRAF.GRA }
  Player: array[1..4] of PlayerRec;   { DS:3897 }
  DoublesCount: integer;              { DS:391F }
  NumPlayers: integer;                { DS:3921 }
  DeedBack, DeedText: integer;        { DS:3923  deed card colours }
  DeedInfoBack, DeedInfoText: integer;
  Unused392B: array[1..6] of byte;    { DS:392B  never referenced }
  Amount: integer;                    { DS:3931  amount to pay/receive }
  Payer, Payee: integer;              { DS:3933 }
  Unused3937: array[1..21] of byte;   { DS:3937  never referenced }
  CardLine: array[1..5] of Str36;     { DS:394C  text of the current card }
  CardTitle: string[20];              { DS:3A05 }
  Unused3A1A: array[1..2] of byte;    { DS:3A1A  never referenced }
  CardTitleCol, CardTextCol, CardBackCol: integer;  { DS:3A1C }
  Prop: array[1..40] of PropRec;      { DS:3A22  ownership of the squares }
  NearestUtil: boolean;               { DS:3AEA  Chance: utility rent = 10 x dice }
  RepeatTurn: boolean;                { DS:3AEB  same player again }
  HasMonopoly: boolean;               { DS:3AEC  result of CheckMonopoly }
  PlayerFound: boolean;               { DS:3AED  result of SelectPlayer }
  MustRaise: boolean;                 { DS:3AEE  payer must raise money first }
  CheckGroup: integer;                { DS:3AEF  input of CheckMonopoly }
  GfxColOfs, PanelOfs: integer;       { DS:3AF1  screen layout for 2..4 players }
  GroupName: string[12];              { DS:3AF5 }
  NearestRR: boolean;                 { DS:3B02  Chance: railroad rent doubled }
  MovedAgain: boolean;                { DS:3B03  a card moved the token: evaluate again }
  PropFound: boolean;                 { DS:3B04  result of SelectProperty }
  Valid: boolean;                     { DS:3B05 }
  Flag: boolean;                      { DS:3B06 }
  SelProp: integer;                   { DS:3B07  property chosen in SelectProperty }
  SelPlayer: integer;                 { DS:3B09  player chosen in SelectPlayer }
  Step: integer;                      { DS:3B0B  counting step / number of railroads }
  RentMult: integer;                  { DS:3B0D }
  AbbrInput: Str5;                    { DS:3B0F  short name typed }
  PlayerInput: string[10];            { DS:3B15  player name typed }
  Assessment: integer;                { DS:3B20  tax / repairs total }
  Units: integer;                     { DS:3B22  houses to buy or return }
  DeedSquare: integer;                { DS:3B24  square whose deed is shown }
  PaidOut, RolledOut: boolean;        { DS:3B26  how the player left jail }
  ChanceDeck, ChestDeck: array[1..16] of integer;  { DS:3B28  card order }
  ChestIndex, ChanceIndex: integer;   { DS:3B68  last card drawn }
  Interest: integer;                  { DS:3B6C }
  AmountDue: integer;                 { DS:3B6E }
  Other: integer;                     { DS:3B70  loop over the other players }
  Creditor, Debtor: integer;          { DS:3B72  bankruptcy (Creditor 0 = bank) }
  SkipBusiness: boolean;              { DS:3B76 }
  GameOver: boolean;                  { DS:3B77 }
  ShowDue: boolean;                   { DS:3B78  show AmountDue in the status window }
  SoundOn: boolean;                   { DS:3B79  toggled with F1 }
  SaveBuf: SaveRec;                   { DS:3B7A }
  NumStr: string[10];                 { DS:5F22 }
{$I MONOCOD1.INC}
{$I MONOCOD2.INC}

label 1, 2, 3;
begin
  StartGame;
1:
  if (DoublesCount = 0) and not RepeatTurn then CurPlayer := CurPlayer + 1;
  if CurPlayer > NumPlayers then CurPlayer := 1;
  if Player[CurPlayer].Bankrupt then goto 1;
  if Player[CurPlayer].Loan > 0 then
  begin
    RepayLoan;
    if not Player[CurPlayer].Bankrupt then RepeatTurn := true;
    goto 1;
  end;
  ShowBoard;
  RepeatTurn := false;
  ShowDue := false;
  ShowTurnGfx;
  if Player[CurPlayer].InJail then
  begin
    JailTurn;
    if Player[CurPlayer].Bankrupt then goto 2;
    if RolledOut and PaidOut then
    begin
      MoveToken;
      goto 3;
    end;
    if PaidOut then
    begin
      RepeatTurn := true;
      goto 1;
    end;
    if RolledOut then MoveToken;
  end
  else
    DiceRoll;
3:
  MovedAgain := false;
  GetPic(Gfx.Board, 0, 0, 122, 122);
  case Player[CurPlayer].Loc of
    2, 4, 7, 9, 10, 12, 14, 15, 17, 19, 20, 22, 24, 25, 27, 28, 30, 32, 33, 35, 38, 40,
    6, 16, 26, 36, 13, 29: PropertySquare;
    3, 18, 34: CommunityChest;
    8, 23, 37: Chance;
    5, 31, 39: TaxSquare;
    1, 11, 21: CornerSquare;
  end;
  if MovedAgain then goto 3;
  if not Player[CurPlayer].Bankrupt then
    if not SkipBusiness then BusinessOrGo;
  SkipBusiness := false;
2:
  if Player[CurPlayer].Bankrupt then
  begin
    DoublesCount := 0;
    RepeatTurn := false;
    ShowBoard;
    CalcTokenXY;
    if Player[CurPlayer].InJail then TokenX := TokenX + 8;
    PutPic(Gfx.Tok3[CurPlayer], TokenX, TokenY);
    GetPic(Gfx.Board, 0, 0, 122, 122);
  end;
  goto 1;
end.
