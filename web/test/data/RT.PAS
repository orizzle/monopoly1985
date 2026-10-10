program rt;
var f: file of real; g: file of integer; a, b, i: integer; q, p, s: real;
begin
  Assign(f, 'REALS.BIN'); Rewrite(f);
  Assign(g, 'INTS.BIN'); Rewrite(g);
  for a := 1 to 60 do
    for b := 1 to 13 do
    begin
      q := (a * 7 + b * 13) / b;
      p := q * 0.1;
      s := 29 - q;
      Write(f, q); Write(f, p); Write(f, s);
      i := Round(p); Write(g, i);
      i := Trunc(p); Write(g, i);
      i := Round(q / 2 * 0.1); Write(g, i);
    end;
  for a := 1 to 400 do
  begin
    i := Round(a / 2 * 0.1); Write(g, i);
    q := a / 2 * 0.1; Write(f, q);
  end;
  q := 0.1; Write(f, q);
  Close(f); Close(g);
end.
